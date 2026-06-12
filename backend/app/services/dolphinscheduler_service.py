import json
import re
import time
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ds_metadata import DSAlertGroup, DSEnvironment, DSProject
from app.models.task import TaskDefinition
from app.schemas.ds import DSConfigRead, DSMetadataOptionsRead
from app.schemas.task import WorkflowTestSummary
from app.services.postgres_service import execute_pg_method_with_job_instance_name

SUCCESS_STATES = {"SUCCESS", "FORCED_SUCCESS", 7, "7"}
FAILED_STATES = {"FAILURE", "STOP", "KILL", "NEED_FAULT_TOLERANCE", 5, 6, 8, 9, "5", "6", "8", "9"}
RUNNING_STATES = {
    "SUBMITTED_SUCCESS",
    "RUNNING_EXECUTION",
    "READY_PAUSE",
    "READY_STOP",
    "DELAY_EXECUTION",
    "SERIAL_WAIT",
    "WAITING_THREAD",
    0,
    1,
    2,
    3,
    4,
    10,
    11,
    12,
    "0",
    "1",
    "2",
    "3",
    "4",
    "10",
    "11",
    "12",
}


class DolphinSchedulerTokenClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.timeout = timeout
        self.api_prefix = self.base_url if self.base_url.endswith("/dolphinscheduler") else f"{self.base_url}/dolphinscheduler"

    def query_process_definition_list(
        self,
        project_code: str,
        page_no: int = 1,
        page_size: int = 10,
        search_val: str = "",
        user_id: int | None = None,
        other_params_json: str = "",
    ) -> dict:
        params = {"pageNo": page_no, "pageSize": page_size}
        if search_val:
            params["searchVal"] = search_val
        if user_id is not None:
            params["userId"] = user_id
        if other_params_json:
            params["otherParamsJson"] = other_params_json
        request = self._build_request(self._build_url(f"/projects/{project_code}/process-definition", params), "GET")
        return self._request_json(request)

    def start_process_instance(
        self,
        project_code: str,
        process_definition_code: str,
        failure_strategy: str = "CONTINUE",
        process_instance_priority: str = "MEDIUM",
        warning_type: str = "NONE",
        schedule_time: str = "",
        worker_group: str = "default",
        exec_type: str = "START_PROCESS",
        start_params: dict | None = None,
        environment_code: int | None = None,
        warning_group_id: int | None = None,
        timeout_value: int | None = None,
    ) -> dict:
        params = {
            "failureStrategy": failure_strategy,
            "processDefinitionCode": process_definition_code,
            "processInstancePriority": process_instance_priority,
            "warningType": warning_type,
            "scheduleTime": schedule_time,
            "workerGroup": worker_group,
            "execType": exec_type,
        }
        if start_params is not None:
            params["startParams"] = json.dumps(start_params, ensure_ascii=False)
        if environment_code is not None:
            params["environmentCode"] = environment_code
        if warning_group_id is not None:
            params["warningGroupId"] = warning_group_id
        if timeout_value is not None:
            params["timeout"] = timeout_value

        request = self._build_request(
            self._build_url(f"/projects/{project_code}/executors/start-process-instance", params),
            "POST",
        )
        return self._request_json(request)

    def query_process_instance_by_id(self, project_code: str, process_instance_id: int) -> dict:
        request = self._build_request(self._build_url(f"/projects/{project_code}/process-instances/{process_instance_id}"), "GET")
        return self._request_json(request)

    def query_process_instance_list(
        self,
        project_code: str,
        page_no: int = 1,
        page_size: int = 50,
        process_define_code: str | None = None,
        search_val: str = "",
        start_date: str = "",
        end_date: str = "",
        state_type: str = "",
    ) -> dict:
        params = {"pageNo": page_no, "pageSize": page_size}
        if process_define_code:
            params["processDefineCode"] = process_define_code
        if search_val:
            params["searchVal"] = search_val
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if state_type:
            params["stateType"] = state_type

        request = self._build_request(self._build_url(f"/projects/{project_code}/process-instances", params), "GET")
        return self._request_json(request)

    def query_current_user(self) -> dict | None:
        candidate_paths = ("/users/get-user-info", "/users/current", "/user/current", "/user/get-user-info")
        for path in candidate_paths:
            try:
                result = self._request_json(self._build_request(self._build_url(path), "GET"))
            except RuntimeError:
                continue

            payload = result.get("data")
            if not isinstance(payload, dict):
                payload = result if isinstance(result, dict) else None
            if not isinstance(payload, dict):
                continue

            user_id = _coerce_int(payload.get("id") or payload.get("userId"))
            username = _normalize_text(payload.get("userName") or payload.get("username") or payload.get("tenantCode"))
            display_name = _normalize_text(payload.get("name") or payload.get("nickName"))
            if user_id is None and not username and not display_name:
                continue

            return {"id": user_id, "username": username, "displayName": display_name}
        return None

    def find_latest_process_instance(
        self,
        project_code: str,
        process_definition_code: str,
        current_user: dict | None,
        launched_after: datetime,
        page_size: int = 50,
    ) -> dict:
        if not current_user:
            raise RuntimeError("启动流程后未直接返回实例 ID，且无法识别当前 Token 对应的 DS 用户，无法安全回查本次实例。")

        result = self.query_process_instance_list(
            project_code=project_code,
            page_no=1,
            page_size=page_size,
            process_define_code=process_definition_code,
        )
        instances = self._extract_total_list(result)
        if not instances:
            raise RuntimeError("未查询到任何流程实例记录。")

        current_user_id = _coerce_int(current_user.get("id"))
        current_names = {
            value.lower()
            for value in (current_user.get("username"), current_user.get("displayName"))
            if isinstance(value, str) and value.strip()
        }
        time_floor = launched_after - timedelta(seconds=10)
        undated_count = 0

        scoped: list[dict] = []
        for item in instances:
            if str(item.get("processDefinitionCode") or "") != str(process_definition_code):
                continue

            executor_id = _coerce_int(item.get("executorId"))
            executor_name = _normalize_text(item.get("executorName"))
            belongs_to_current_user = False
            if current_user_id is not None and executor_id == current_user_id:
                belongs_to_current_user = True
            elif executor_name and executor_name.lower() in current_names:
                belongs_to_current_user = True
            if not belongs_to_current_user:
                continue

            instance_time = _extract_instance_time(item)
            if instance_time is None:
                undated_count += 1
                continue
            if instance_time < time_floor:
                continue
            scoped.append(item)

        if not scoped:
            if undated_count:
                raise RuntimeError(
                    "已查询流程实例列表，但候选实例缺少可识别的启动时间，无法安全确认本次启动的实例。"
                )
            raise RuntimeError("已查询流程实例列表，但没有找到本次启动后由当前 Token 用户创建的实例记录。")

        return max(scoped, key=self._sort_key_for_instance)

    def start_existing_workflow_and_get_instance(
        self,
        project_code: str,
        process_definition_code: str,
        failure_strategy: str = "CONTINUE",
        process_instance_priority: str = "MEDIUM",
        warning_type: str = "NONE",
        schedule_time: str = "",
        worker_group: str = "default",
        exec_type: str = "START_PROCESS",
        start_params: dict | None = None,
        environment_code: int | None = None,
        warning_group_id: int | None = None,
        timeout_value: int | None = None,
        poll_attempts: int = 6,
        poll_interval_seconds: float = 1.0,
        result_poll_interval_seconds: float = 5.0,
        result_poll_timeout_seconds: float | None = None,
    ) -> dict:
        launched_at = datetime.now()
        current_user: dict | None = None
        start_result = self.start_process_instance(
            project_code=project_code,
            process_definition_code=process_definition_code,
            failure_strategy=failure_strategy,
            process_instance_priority=process_instance_priority,
            warning_type=warning_type,
            schedule_time=schedule_time,
            worker_group=worker_group,
            exec_type=exec_type,
            start_params=start_params,
            environment_code=environment_code,
            warning_group_id=warning_group_id,
            timeout_value=timeout_value,
        )

        process_instance_id = self._extract_process_instance_id(start_result)
        instance: dict | None = None

        if process_instance_id is not None:
            for attempt in range(poll_attempts):
                try:
                    detail_result = self.query_process_instance_by_id(project_code, process_instance_id)
                    if isinstance(detail_result.get("data"), dict):
                        instance = detail_result["data"]
                        break
                except Exception:
                    if attempt == poll_attempts - 1:
                        raise
                    time.sleep(poll_interval_seconds)
        else:
            current_user = self.query_current_user()
            for attempt in range(poll_attempts):
                try:
                    instance = self.find_latest_process_instance(
                        project_code=project_code,
                        process_definition_code=process_definition_code,
                        current_user=current_user,
                        launched_after=launched_at,
                    )
                except Exception:
                    if attempt == poll_attempts - 1:
                        raise
                    time.sleep(poll_interval_seconds)
                    continue
                if isinstance(instance, dict):
                    process_instance_id = _coerce_int(instance.get("id"))
                    if process_instance_id is not None:
                        try:
                            detail_result = self.query_process_instance_by_id(project_code, process_instance_id)
                            if isinstance(detail_result.get("data"), dict):
                                instance = detail_result["data"]
                        except Exception:
                            pass
                    break
                time.sleep(poll_interval_seconds)

        if not isinstance(instance, dict):
            raise RuntimeError("流程已启动，但未能在轮询窗口内获取到实例详情。")

        process_instance_id = process_instance_id or _coerce_int(instance.get("id"))
        instance = self._wait_for_terminal_process_instance(
            project_code=project_code,
            process_instance_id=process_instance_id,
            fallback_instance=instance,
            poll_interval_seconds=result_poll_interval_seconds,
            timeout_seconds=result_poll_timeout_seconds,
        )
        instance = self._ensure_executor_fields(instance, current_user)

        return {
            "start_result": start_result,
            "process_instance": instance,
            "summary": self._build_summary(instance, process_instance_id),
        }

    def _ensure_executor_fields(self, instance: dict, current_user: dict | None = None) -> dict:
        if _normalize_text(instance.get("executorName")) and _coerce_int(instance.get("executorId")) is not None:
            return instance

        user = current_user
        if user is None:
            try:
                user = self.query_current_user()
            except RuntimeError:
                user = None
        if not user:
            return instance

        enriched = dict(instance)
        if _coerce_int(enriched.get("executorId")) is None:
            executor_id = _coerce_int(user.get("id"))
            if executor_id is not None:
                enriched["executorId"] = executor_id
        if not _normalize_text(enriched.get("executorName")):
            enriched["executorName"] = _normalize_text(user.get("username")) or _normalize_text(user.get("displayName"))
        return enriched

    def _wait_for_terminal_process_instance(
        self,
        project_code: str,
        process_instance_id: int | None,
        fallback_instance: dict,
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float | None = None,
    ) -> dict:
        if process_instance_id is None:
            raise RuntimeError("流程已启动，但无法获取流程实例 ID，无法持续查询最终状态。")

        started_at = time.monotonic()
        instance = fallback_instance
        last_error: Exception | None = None

        while True:
            state_status = classify_workflow_state(instance.get("state") if isinstance(instance, dict) else None)
            if state_status in ("SUCCEEDED", "FAILED"):
                return instance

            if timeout_seconds is not None and time.monotonic() - started_at >= timeout_seconds:
                state = instance.get("state") if isinstance(instance, dict) else "-"
                if last_error is not None:
                    raise RuntimeError(f"等待流程实例 {process_instance_id} 结束超时，最近一次查询失败：{last_error}") from last_error
                raise RuntimeError(f"等待流程实例 {process_instance_id} 结束超时，当前状态 {state}。")

            time.sleep(poll_interval_seconds)
            try:
                detail_result = self.query_process_instance_by_id(project_code, process_instance_id)
                if isinstance(detail_result.get("data"), dict):
                    instance = detail_result["data"]
                    last_error = None
            except Exception as exc:
                last_error = exc

    def _build_request(self, url: str, method: str) -> Request:
        return Request(url=url, method=method, headers={"Accept": "application/json", "token": self.token})

    def _build_url(self, path: str, params: dict | None = None) -> str:
        url = f"{self.api_prefix}{path}"
        return f"{url}?{urlencode(params)}" if params else url

    def _request_json(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"DolphinScheduler HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"DolphinScheduler network error: {exc.reason}") from exc

        try:
            result = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"DolphinScheduler returned invalid JSON: {payload}") from exc

        if result.get("code") not in (0, 200) and not result.get("success", False):
            raise RuntimeError(result.get("msg") or f"DolphinScheduler call failed: {result}")
        return result

    @staticmethod
    def _extract_process_instance_id(result: dict) -> int | None:
        data = result.get("data")
        if isinstance(data, int):
            return data
        if isinstance(data, str) and data.isdigit():
            return int(data)
        if isinstance(data, dict):
            for key in ("processInstanceId", "process_instance_id", "id", "instanceId"):
                value = data.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return None

    @staticmethod
    def _extract_total_list(result: dict) -> list[dict]:
        data = result.get("data")
        if isinstance(data, dict):
            total_list = data.get("totalList")
            if isinstance(total_list, list):
                return [item for item in total_list if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    @staticmethod
    def _sort_key_for_instance(instance: dict) -> tuple[datetime, datetime, int]:
        command_start_time = _extract_datetime_value(instance.get("commandStartTime")) or datetime.min
        start_time = _extract_datetime_value(instance.get("startTime")) or datetime.min
        instance_id = _coerce_int(instance.get("id")) or 0
        return (command_start_time, start_time, instance_id)

    @staticmethod
    def _build_summary(instance: dict, fallback_id: int | None) -> dict:
        return {
            "processInstanceId": _coerce_int(instance.get("id")) or fallback_id,
            "processInstanceName": instance.get("name"),
            "processInstanceState": instance.get("state"),
            "processDefinitionCode": instance.get("processDefinitionCode"),
            "startTime": _stringify_datetime(instance.get("startTime")),
            "endTime": _stringify_datetime(instance.get("endTime")),
            "host": _normalize_text(instance.get("host")),
            "executorId": _coerce_int(instance.get("executorId")),
            "executorName": _normalize_text(instance.get("executorName")),
        }


def get_ds_config(db: Session) -> DSConfigRead:
    return DSConfigRead(
        id=0,
        baseUrl=_normalize_config_text(settings.dolphinscheduler_base_url).rstrip("/"),
        defaultProjectCode=_normalize_config_text(settings.dolphinscheduler_project_code) or None,
        workerGroup=_normalize_config_text(settings.dolphinscheduler_worker_group) or "default",
        timeoutSeconds=settings.dolphinscheduler_timeout_seconds,
        enabled=settings.dolphinscheduler_enabled,
        failureStrategy=_normalize_config_text(settings.dolphinscheduler_failure_strategy) or "CONTINUE",
        processInstancePriority=_normalize_config_text(settings.dolphinscheduler_process_instance_priority) or "MEDIUM",
        warningType=_normalize_config_text(settings.dolphinscheduler_warning_type) or "NONE",
        execType=_normalize_config_text(settings.dolphinscheduler_exec_type) or "START_PROCESS",
        defaultEnvironmentCode=_normalize_config_text(settings.dolphinscheduler_environment_code) or None,
        defaultWarningGroupId=_normalize_config_text(settings.dolphinscheduler_warning_group_id) or None,
        defaultDsCallbackMethod=_normalize_config_text(settings.task_default_ds_callback_method),
        defaultPgCallbackMethod=_normalize_config_text(settings.task_default_pg_callback_method),
        tokenConfigured=bool(_normalize_config_text(settings.dolphinscheduler_access_token)),
        lastTestStatus=None,
        lastTestMessage=None,
        lastTestedAt=None,
        updatedAt=datetime.utcnow(),
    )


def get_ds_metadata_options(db: Session) -> DSMetadataOptionsRead:
    projects = db.query(DSProject).order_by(DSProject.id.asc()).all()
    environments = db.query(DSEnvironment).order_by(DSEnvironment.id.asc()).all()
    warning_groups = db.query(DSAlertGroup).order_by(DSAlertGroup.id.asc()).all()
    warning_group_options = [
        {
            "id": item.id,
            "name": item.group_name,
            "groupName": item.group_name,
            "alertInstanceIds": item.alert_instance_ids,
        }
        for item in warning_groups
    ]
    return DSMetadataOptionsRead(
        projects=projects,
        environments=environments,
        warningGroups=warning_group_options,
    )


def start_ds_workflow_and_get_summary(
    db: Session,
    *,
    task_name: str,
    process_definition_code: str,
    request_parameters: dict | None,
    callback_method: str | None = None,
) -> tuple[WorkflowTestSummary, str, str]:
    client, config = _build_enabled_client(db)
    workflow_request = _normalize_workflow_request(process_definition_code, request_parameters or {}, config)

    result = client.start_existing_workflow_and_get_instance(
        project_code=workflow_request["projectCode"],
        process_definition_code=workflow_request["processDefinitionCode"],
        failure_strategy=workflow_request["failureStrategy"],
        process_instance_priority=workflow_request["processInstancePriority"],
        warning_type=workflow_request["warningType"],
        schedule_time=workflow_request["scheduleTime"],
        worker_group=workflow_request["workerGroup"],
        exec_type=workflow_request["execType"],
        start_params=workflow_request["startParams"],
        environment_code=workflow_request["environmentCode"],
        warning_group_id=workflow_request["warningGroupId"],
    )

    summary = WorkflowTestSummary.model_validate(result["summary"])
    state_status = classify_workflow_state(summary.process_instance_state)
    message = _build_workflow_message(task_name, summary, state_status)
    if state_status == "SUCCEEDED" and callback_method and callback_method.strip():
        callback_result = execute_pg_method_with_job_instance_name(
            callback_method.strip(),
            summary.process_instance_name,
        )
        message = f"{message} 后置方法执行：{callback_result}"
    return summary, state_status, message


def execute_ds_task(db: Session, execution, task: TaskDefinition) -> tuple[str, str]:
    summary, state_status, message = start_ds_workflow_and_get_summary(
        db,
        task_name=task.display_name,
        process_definition_code=str(task.engine_target),
        request_parameters=dict(execution.request_parameters or {}),
        callback_method=task.ds_callback_method,
    )
    external_instance_id = str(summary.process_instance_id or f"ds-{execution.id:06d}")
    if state_status != "SUCCEEDED":
        raise RuntimeError(message)
    return external_instance_id, message


def build_execution_request_parameters(task: TaskDefinition) -> dict:
    parameters = task.parameter_template or {}
    if isinstance(parameters, dict):
        rendered = dict(parameters)
        if task.engine_type == "DS" and "workerGroup" not in rendered:
            rendered["workerGroup"] = _normalize_config_text(settings.dolphinscheduler_worker_group) or "default"
        return rendered
    return {}


def classify_workflow_state(state: str | int | None) -> str:
    if state in SUCCESS_STATES:
        return "SUCCEEDED"
    if state in FAILED_STATES:
        return "FAILED"
    if state in RUNNING_STATES or state is not None:
        return "RUNNING"
    return "UNKNOWN"


def _build_enabled_client(db: Session) -> tuple[DolphinSchedulerTokenClient, dict]:
    if not settings.dolphinscheduler_enabled:
        raise RuntimeError("DS 连接配置未启用，请在 .env 中设置 DOLPHINSCHEDULER_ENABLED=true。")
    base_url = _normalize_config_text(settings.dolphinscheduler_base_url).rstrip("/")
    if not base_url:
        raise RuntimeError("DS 连接配置缺少 DOLPHINSCHEDULER_BASE_URL。")
    token = _normalize_config_text(settings.dolphinscheduler_access_token)
    if not token:
        raise RuntimeError("DS 连接配置缺少 DOLPHINSCHEDULER_ACCESS_TOKEN。")
    config = {
        "defaultProjectCode": _normalize_config_text(settings.dolphinscheduler_project_code),
        "workerGroup": _normalize_config_text(settings.dolphinscheduler_worker_group) or "default",
    }
    return DolphinSchedulerTokenClient(base_url, token, settings.dolphinscheduler_timeout_seconds), config


def _normalize_workflow_request(process_definition_code: str, request_parameters: dict, config: dict) -> dict:
    project_code = _normalize_text(request_parameters.get("projectCode")) or _normalize_text(config.get("defaultProjectCode"))
    process_code = _normalize_text(request_parameters.get("processDefinitionCode")) or _normalize_text(process_definition_code)
    missing_fields = []
    if not project_code:
        missing_fields.append("projectCode（项目编码，可来自任务配置或 DS 连接配置的默认项目编码）")
    if not process_code:
        missing_fields.append("processDefinitionCode（流程定义编码）")
    if missing_fields:
        raise RuntimeError(f"DS 任务启动参数缺失：{'；'.join(missing_fields)}。")

    start_params = request_parameters.get("startParams")
    if isinstance(start_params, str) and start_params.strip():
        try:
            start_params = json.loads(start_params)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DS 任务的 startParams 不是合法 JSON。") from exc
    if start_params in ("", None):
        start_params = None
    if start_params is not None and not isinstance(start_params, dict):
        raise RuntimeError("DS 任务的 startParams 必须是对象。")

    return {
        "projectCode": project_code,
        "processDefinitionCode": process_code,
        "failureStrategy": _normalize_text(request_parameters.get("failureStrategy")) or _normalize_config_text(settings.dolphinscheduler_failure_strategy) or "CONTINUE",
        "processInstancePriority": _normalize_text(request_parameters.get("processInstancePriority")) or _normalize_config_text(settings.dolphinscheduler_process_instance_priority) or "MEDIUM",
        "warningType": _normalize_text(request_parameters.get("warningType")) or _normalize_config_text(settings.dolphinscheduler_warning_type) or "NONE",
        "scheduleTime": _normalize_text(request_parameters.get("scheduleTime")) or "",
        "workerGroup": _normalize_text(request_parameters.get("workerGroup")) or config.get("workerGroup") or "default",
        "execType": _normalize_text(request_parameters.get("execType")) or _normalize_config_text(settings.dolphinscheduler_exec_type) or "START_PROCESS",
        "startParams": start_params,
        "environmentCode": _coerce_int(request_parameters.get("environmentCode")) or _normalize_config_int(settings.dolphinscheduler_environment_code),
        "warningGroupId": _coerce_int(request_parameters.get("warningGroupId")) or _normalize_config_int(settings.dolphinscheduler_warning_group_id),
    }


def _build_workflow_message(task_name: str, summary: WorkflowTestSummary, state_status: str) -> str:
    instance_name = summary.process_instance_name or "-"
    state = summary.process_instance_state or "-"
    if state_status == "SUCCEEDED":
        return f"{task_name} 执行成功，实例名称 {instance_name} 当前状态 {state}。"
    if state_status == "FAILED":
        return f"{task_name} 执行失败，实例名称 {instance_name} 当前状态 {state}。"
    return f"{task_name} 已启动，但实例名称 {instance_name} 当前状态为 {state}，未达到成功状态。"


def _extract_instance_time(instance: dict) -> datetime | None:
    for key in ("commandStartTime", "startTime", "submitTime", "createTime"):
        parsed = _extract_datetime_value(instance.get(key))
        if parsed is not None:
            return parsed
    return _extract_datetime_from_instance_name(instance.get("name"))


def _extract_datetime_from_instance_name(value) -> datetime | None:
    text = _normalize_text(value)
    if not text:
        return None

    matches = re.findall(r"(?<!\d)(\d{14,17})(?!\d)", text)
    if not matches:
        return None

    token = matches[-1]
    base = token[:14]
    try:
        parsed = datetime.strptime(base, "%Y%m%d%H%M%S")
    except ValueError:
        return None

    if len(token) > 14:
        microseconds = int(token[14:].ljust(6, "0")[:6])
        parsed = parsed.replace(microsecond=microseconds)
    return parsed


def _extract_datetime_value(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    normalized = text.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _coerce_int(value) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _normalize_config_int(value) -> int | None:
    return _coerce_int(_normalize_config_text(value))


def _normalize_config_text(value) -> str:
    normalized = _normalize_text(value) or ""
    if normalized.startswith("#"):
        return ""
    return normalized


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stringify_datetime(value) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return _normalize_text(value)
