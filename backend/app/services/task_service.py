import hashlib
import json
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.current_user import CurrentUser
from app.models.execution import TaskExecution
from app.models.task import TaskDefinition, TaskDirectory, task_execute_user, task_notify_user, task_visible_user
from app.models.user import User
from app.schemas.task import (
    AdminTaskListItem,
    AdminTaskPage,
    AdminTaskRead,
    BusinessTaskRead,
    TaskDirectoryCreate,
    TaskDirectoryRead,
    TaskDirectoryUpdate,
    TaskExecutionTestResult,
    TaskUpsert,
)
from app.services.audit_service import write_audit_log
from app.services.cron_window import cron_matches_now, validate_cron_expression
from app.services.dolphinscheduler_service import start_ds_workflow_and_get_summary
from app.services.postgres_service import (
    build_job_instance_name,
    execute_pg_method_with_job_instance_name,
    execute_pg_procedure,
    normalize_pg_call_statements,
    normalize_pg_method_statement,
    render_optional_job_instance_name_argument,
)
from app.services.report_user_service import ReportUser, get_report_user_map, normalize_email

TESTED_TASK_PAYLOADS: dict[str, dict] = {}


def execute_pg_task_with_job_instance_name(
    procedure_statement: str,
    *,
    task_name: str,
    callback_method: str | None = None,
) -> tuple[str, str]:
    job_instance_name = build_job_instance_name(task_name)
    rendered_procedure = render_optional_job_instance_name_argument(procedure_statement, job_instance_name)
    execute_pg_procedure(rendered_procedure)
    if callback_method and callback_method.strip():
        execute_pg_method_with_job_instance_name(callback_method.strip(), job_instance_name)
    return job_instance_name, f"成功，{job_instance_name}"


def get_visible_tasks(db: Session, user: CurrentUser | User) -> list[BusinessTaskRead]:
    tasks = (
        db.query(TaskDefinition)
        .options(
            selectinload(TaskDefinition.directory),
        )
        .filter(TaskDefinition.published.is_(True), TaskDefinition.in_task_center.is_(True))
        .order_by(TaskDefinition.id.asc())
        .all()
    )
    result: list[BusinessTaskRead] = []
    for item in tasks:
        if _task_visible_to_user(db, item, user):
            schema = BusinessTaskRead.model_validate(item)
            schema.directory_name = item.directory.directory_name if item.directory else None
            schema.directory_path = _build_directory_path(item.directory) if item.directory else None
            executable_people = _get_task_people(db, item.id, task_execute_user)
            schema.can_execute = _task_executable_by_user(db, item, user)
            schema.executable_user_names = [person["fullname"] for person in executable_people]
            schema.executable_user_emails = [person["email"] for person in executable_people]
            result.append(schema)
    return sorted(result, key=lambda item: int(item.task_code))


def list_all_tasks(db: Session) -> list[AdminTaskRead]:
    tasks = (
        db.query(TaskDefinition)
        .options(
            selectinload(TaskDefinition.directory),
        )
        .order_by(TaskDefinition.id.asc())
        .all()
    )
    schemas = [_to_admin_schema(db, item) for item in tasks]
    return sorted(schemas, key=lambda item: int(item.task_code))


def list_admin_tasks(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    engine_type: str | None = None,
    directory_id: int | None = None,
    uncategorized: bool = False,
) -> AdminTaskPage:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = db.query(TaskDefinition).options(selectinload(TaskDefinition.directory))

    keyword_text = (keyword or "").strip()
    if keyword_text:
        pattern = f"%{keyword_text}%"
        query = query.filter(
            or_(
                TaskDefinition.display_name.ilike(pattern),
                TaskDefinition.task_code.ilike(pattern),
            )
        )

    engine_text = (engine_type or "").strip().upper()
    if engine_text in {"DS", "PG"}:
        query = query.filter(TaskDefinition.engine_type == engine_text)

    if uncategorized:
        query = query.filter(TaskDefinition.directory_id.is_(None))
    elif directory_id is not None:
        directory_ids = _collect_directory_ids(db, directory_id)
        query = query.filter(TaskDefinition.directory_id.in_(directory_ids))

    total = query.count()
    tasks = (
        query
        .order_by(TaskDefinition.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AdminTaskPage(
        items=[_to_admin_list_item(item) for item in tasks],
        total=total,
        page=page,
        pageSize=page_size,
    )


def get_admin_task(db: Session, task_id: int) -> AdminTaskRead:
    task = (
        db.query(TaskDefinition)
        .options(selectinload(TaskDefinition.directory))
        .filter(TaskDefinition.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在。")
    return _to_admin_schema(db, task)


def list_available_tasks_for_center(
    db: Session,
    *,
    keyword: str | None = None,
    limit: int = 100,
) -> list[AdminTaskListItem]:
    limit = min(max(limit, 1), 200)
    query = (
        db.query(TaskDefinition)
        .options(selectinload(TaskDefinition.directory))
        .filter(
            TaskDefinition.published.is_(True),
            TaskDefinition.in_task_center.is_(False),
        )
    )
    keyword_text = (keyword or "").strip()
    if keyword_text:
        pattern = f"%{keyword_text}%"
        query = query.filter(
            or_(
                TaskDefinition.display_name.ilike(pattern),
                TaskDefinition.task_code.ilike(pattern),
            )
        )
    tasks = query.order_by(TaskDefinition.id.asc()).limit(limit).all()
    return [_to_admin_list_item(item) for item in tasks]


def list_task_directories(db: Session) -> list[TaskDirectoryRead]:
    directories = (
        db.query(TaskDirectory)
        .order_by(TaskDirectory.sort_order.asc(), TaskDirectory.id.asc())
        .all()
    )
    ordered = _sort_directories_as_tree(directories)
    return [_to_directory_schema(item) for item in ordered]


def list_visible_task_directories(db: Session, user: CurrentUser | User) -> list[TaskDirectoryRead]:
    if user.has_role("ADMIN"):
        return list_task_directories(db)

    directories = (
        db.query(TaskDirectory)
        .order_by(TaskDirectory.sort_order.asc(), TaskDirectory.id.asc())
        .all()
    )
    directory_by_id = {item.id: item for item in directories}
    tasks = (
        db.query(TaskDefinition)
        .filter(TaskDefinition.published.is_(True), TaskDefinition.in_task_center.is_(True))
        .all()
    )

    visible_directory_ids: set[int] = set()
    for task in tasks:
        if task.directory_id is None or not _task_visible_to_user(db, task, user):
            continue
        current = directory_by_id.get(task.directory_id)
        while current:
            visible_directory_ids.add(current.id)
            current = directory_by_id.get(current.parent_id) if current.parent_id is not None else None

    ordered = _sort_directories_as_tree([item for item in directories if item.id in visible_directory_ids])
    return [_to_directory_schema(item) for item in ordered]


def create_task_directory(db: Session, payload: TaskDirectoryCreate, operator: User) -> TaskDirectoryRead:
    directory_name = payload.directory_name.strip()
    if not directory_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="目录名称不能为空。")
    duplicate = db.query(TaskDirectory).filter(TaskDirectory.directory_name == directory_name).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"目录“{directory_name}”已存在。")
    parent = None
    if payload.parent_id is not None:
        parent = db.get(TaskDirectory, payload.parent_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="父级目录不存在。")
        if parent.parent_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="最多只能创建到三级目录。")

    siblings = db.query(TaskDirectory).filter(TaskDirectory.parent_id == payload.parent_id).all()
    max_sort_order = max([item.sort_order for item in siblings] or [0])
    directory = TaskDirectory(
        parent_id=payload.parent_id,
        directory_name=directory_name,
        sort_order=max_sort_order + 10,
    )
    db.add(directory)
    write_audit_log(
        db,
        action_code="TASK_DIRECTORY_CREATE",
        operator_id=operator.id,
        detail=f"创建任务目录 {directory_name}。",
    )
    db.commit()
    db.refresh(directory)
    return _to_directory_schema(directory)


def update_task_directory(db: Session, directory_id: int, payload: TaskDirectoryUpdate, operator: User) -> TaskDirectoryRead:
    directory = db.get(TaskDirectory, directory_id)
    if not directory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务目录不存在。")

    directory_name = payload.directory_name.strip()
    if not directory_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="目录名称不能为空。")
    duplicate = db.query(TaskDirectory).filter(TaskDirectory.directory_name == directory_name).first()
    if duplicate and duplicate.id != directory.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"目录“{directory_name}”已存在。")

    old_name = directory.directory_name
    directory.directory_name = directory_name
    write_audit_log(
        db,
        action_code="TASK_DIRECTORY_UPDATE",
        operator_id=operator.id,
        detail=f"重命名任务目录 {old_name} 为 {directory_name}。",
    )
    db.commit()
    db.refresh(directory)
    return _to_directory_schema(directory)


def delete_task_directory(db: Session, directory_id: int, operator: User) -> dict:
    directory = db.get(TaskDirectory, directory_id)
    if not directory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务目录不存在。")

    directory_name = directory.directory_name
    directory_ids = _collect_directory_ids(db, directory.id)
    db.query(TaskDefinition).filter(TaskDefinition.directory_id.in_(directory_ids)).update(
        {TaskDefinition.directory_id: None},
        synchronize_session=False,
    )
    for child_id in sorted(directory_ids, reverse=True):
        child = db.get(TaskDirectory, child_id)
        if child:
            db.delete(child)
    write_audit_log(
        db,
        action_code="TASK_DIRECTORY_DELETE",
        operator_id=operator.id,
        detail=f"删除任务目录 {directory_name}，目录下任务已调整为未分类。",
    )
    db.commit()
    return {"success": True}


def upsert_task(db: Session, payload: TaskUpsert, operator: User) -> AdminTaskRead:
    task, is_create = _persist_task(db, payload)
    write_audit_log(
        db,
        action_code="TASK_CONFIG_UPSERT",
        operator_id=operator.id,
        detail=f"{'创建' if is_create else '更新'}任务 {task.display_name}({task.task_code})。",
    )
    db.commit()
    db.refresh(task)
    return _to_admin_schema(db, task)


def delete_task(db: Session, task_id: int, operator: User) -> dict:
    task = (
        db.query(TaskDefinition)
        .filter(TaskDefinition.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在。")

    task_name = task.display_name
    task_code = task.task_code
    _clear_task_people(db, task.id)
    db.query(TaskExecution).filter(TaskExecution.task_id == task.id).delete()
    deleted_code = int(task.task_code)
    db.delete(task)
    db.flush()
    _shift_task_codes_after_delete(db, deleted_code)
    write_audit_log(
        db,
        action_code="TASK_CONFIG_DELETE",
        operator_id=operator.id,
        detail=f"删除任务 {task_name}({task_code})，并自动重排后续任务编码。",
    )
    db.commit()
    return {"success": True}


def add_task_to_center(db: Session, task_id: int, operator: User) -> AdminTaskRead:
    task = db.get(TaskDefinition, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在。")
    if not task.published:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务需先发布后才能添加到任务中心。")

    task.in_task_center = True
    write_audit_log(
        db,
        action_code="TASK_CENTER_ADD",
        operator_id=operator.id,
        detail=f"添加任务 {task.display_name}({task.task_code}) 到任务中心。",
    )
    db.commit()
    db.refresh(task)
    return _to_admin_schema(db, task)


def remove_task_from_center(db: Session, task_id: int, operator: User) -> AdminTaskRead:
    task = db.get(TaskDefinition, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在。")

    task.in_task_center = False
    write_audit_log(
        db,
        action_code="TASK_CENTER_REMOVE",
        operator_id=operator.id,
        detail=f"从任务中心移除任务 {task.display_name}({task.task_code})。",
    )
    db.commit()
    db.refresh(task)
    return _to_admin_schema(db, task)


def test_task_configuration(db: Session, payload: TaskUpsert, operator: User) -> TaskExecutionTestResult:
    draft_payload = payload.model_copy(update={"published": False})
    payload_hash = _build_task_payload_hash(draft_payload)
    tested_at = datetime.utcnow()

    try:
        if draft_payload.engine_type == "PG":
            job_instance_name, message = execute_pg_task_with_job_instance_name(
                str(draft_payload.engine_target),
                task_name=draft_payload.display_name,
                callback_method=draft_payload.pg_callback_method,
            )
            TESTED_TASK_PAYLOADS[payload_hash] = {
                "success": True,
                "message": message,
                "state": "SUCCEEDED",
                "tested_at": tested_at,
                "workflow_summary": None,
            }
            write_audit_log(
                db,
                action_code="TASK_CONFIG_TEST",
                operator_id=operator.id,
                detail=f"测试 PG 存储过程任务配置 {draft_payload.display_name}({draft_payload.task_code}) 成功：{job_instance_name}。",
            )
            db.commit()
            return TaskExecutionTestResult(
                success=True,
                message=message,
                state="SUCCEEDED",
                task=None,
                workflowSummary=None,
            )

        if draft_payload.engine_type != "DS":
            raise RuntimeError("仅支持 DS 工作流或 PG 存储过程执行测试。")

        workflow_summary, workflow_status, message = start_ds_workflow_and_get_summary(
            db,
            task_name=draft_payload.display_name,
            process_definition_code=str(draft_payload.engine_target),
            request_parameters=draft_payload.parameter_template or {},
            callback_method=draft_payload.ds_callback_method,
        )
        success = workflow_status == "SUCCEEDED"
        if success:
            TESTED_TASK_PAYLOADS[payload_hash] = {
                "success": True,
                "message": message,
                "state": None if workflow_summary.process_instance_state is None else str(workflow_summary.process_instance_state),
                "tested_at": tested_at,
                "workflow_summary": workflow_summary.model_dump(by_alias=True),
            }
        else:
            TESTED_TASK_PAYLOADS.pop(payload_hash, None)
        write_audit_log(
            db,
            action_code="TASK_CONFIG_TEST",
            operator_id=operator.id,
            detail=(
                f"测试任务配置 {draft_payload.display_name}({draft_payload.task_code})，"
                f"实例 {workflow_summary.process_instance_id} 状态 {workflow_summary.process_instance_state}。"
            ),
        )
        db.commit()
        return TaskExecutionTestResult(
            success=success,
            message="执行测试成功，可以继续发布到任务中心。" if success else message,
            state=workflow_summary.process_instance_state,
            task=None,
            workflowSummary=workflow_summary,
        )
    except Exception as exc:
        TESTED_TASK_PAYLOADS.pop(payload_hash, None)
        write_audit_log(
            db,
            action_code="TASK_CONFIG_TEST",
            operator_id=operator.id,
            detail=f"测试任务配置 {draft_payload.display_name}({draft_payload.task_code}) 失败：{exc}",
        )
        db.commit()
        return TaskExecutionTestResult(
            success=False,
            message=str(exc),
            state=None,
            task=None,
            workflowSummary=None,
        )


def _persist_task(db: Session, payload: TaskUpsert) -> tuple[TaskDefinition, bool]:
    task = db.get(TaskDefinition, payload.id) if payload.id else None
    is_create = task is None
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="任务名称不能为空。",
        )
    duplicate = db.query(TaskDefinition).filter(TaskDefinition.display_name == display_name).first()
    if duplicate and (is_create or duplicate.id != task.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"任务名称“{display_name}”已存在，请使用唯一任务名称。",
        )
    engine_target = payload.engine_target.strip()
    if not engine_target:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="执行目标不能为空。",
        )
    if payload.engine_type == "PG":
        try:
            normalize_pg_call_statements(engine_target)
            if payload.pg_callback_method:
                normalize_pg_method_statement(payload.pg_callback_method)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    execution_window_cron = _validate_execution_window_cron(payload.execution_window_cron)
    if is_create:
        task = TaskDefinition(task_code=_get_next_task_code(db))
        db.add(task)
    else:
        task.task_code = task.task_code or _get_next_task_code(db)

    payload_hash = _build_task_payload_hash(payload)
    execution_config_changed = bool(task.last_test_payload_hash and task.last_test_payload_hash != payload_hash)
    if execution_config_changed:
        _clear_test_result(task)

    cached_test_result = TESTED_TASK_PAYLOADS.get(payload_hash)
    if payload.engine_type in {"DS", "PG"} and payload.published:
        tested_current_payload = task.last_test_success and task.last_test_payload_hash == payload_hash
        if not tested_current_payload and not cached_test_result:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="任务必须先对当前执行配置测试成功后，才能发布。",
            )

    task.display_name = display_name
    if payload.directory_id is not None and not db.get(TaskDirectory, payload.directory_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="任务目录不存在。")
    task.directory_id = payload.directory_id
    task.description = payload.description
    task.scenario = payload.scenario
    task.prerequisite = payload.prerequisite
    task.impact_scope = payload.impact_scope
    task.failure_contact = payload.failure_contact
    task.engine_type = payload.engine_type
    task.engine_target = engine_target
    task.ds_callback_method = payload.ds_callback_method.strip() if payload.ds_callback_method else None
    task.pg_callback_method = payload.pg_callback_method.strip() if payload.pg_callback_method else None
    task.parameter_template = payload.parameter_template
    task.repeat_window_minutes = payload.repeat_window_minutes or 0
    task.execution_window_cron = execution_window_cron
    if payload.published:
        task.published = True
    elif is_create or execution_config_changed:
        task.published = False
    if payload.published and cached_test_result:
        _apply_test_result(task, payload_hash, cached_test_result)
    db.flush()
    _replace_task_people(
        db,
        task.id,
        task_visible_user,
        _resolve_payload_people(payload.visible_user_emails),
    )
    _replace_task_people(
        db,
        task.id,
        task_execute_user,
        _resolve_payload_people(payload.executable_user_emails),
    )
    _replace_task_people(
        db,
        task.id,
        task_notify_user,
        _resolve_payload_people(payload.notify_user_emails),
    )
    return task, is_create


def _build_task_payload_hash(payload: TaskUpsert) -> str:
    normalized = {
        "engineType": payload.engine_type,
        "engineTarget": payload.engine_target,
        "dsCallbackMethod": payload.ds_callback_method,
        "pgCallbackMethod": payload.pg_callback_method,
        "parameterTemplate": payload.parameter_template,
    }
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clear_test_result(task: TaskDefinition):
    task.last_test_success = None
    task.last_test_message = None
    task.last_test_state = None
    task.last_tested_at = None
    task.last_test_payload_hash = None
    task.last_test_workflow_summary = None


def _apply_test_result(task: TaskDefinition, payload_hash: str, result: dict):
    task.last_test_success = bool(result.get("success"))
    task.last_test_message = result.get("message")
    task.last_test_state = result.get("state")
    task.last_tested_at = result.get("tested_at")
    task.last_test_payload_hash = payload_hash
    task.last_test_workflow_summary = result.get("workflow_summary")


def _get_next_task_code(db: Session) -> str:
    tasks = db.query(TaskDefinition).order_by(TaskDefinition.id.asc()).all()
    if not tasks:
        return "1"
    return str(max(int(task.task_code) for task in tasks) + 1)


def _shift_task_codes_after_delete(db: Session, deleted_code: int):
    tasks = db.query(TaskDefinition).order_by(TaskDefinition.id.asc()).all()
    for task in tasks:
        current_code = int(task.task_code)
        if current_code > deleted_code:
            task.task_code = str(current_code - 1)
    db.flush()


def _resolve_payload_people(emails: list[str]) -> list[dict[str, str]]:
    report_users = get_report_user_map()
    selected_emails = [normalize_email(email) for email in emails if normalize_email(email)]

    people: list[dict[str, str]] = []
    seen: set[str] = set()
    for email in selected_emails:
        if email in seen:
            continue
        seen.add(email)
        report_user = report_users.get(email)
        fullname = report_user.fullname if report_user else email
        people.append({"email": email, "fullname": fullname, "display": _format_person(fullname, email)})
    return people


def _replace_task_people(db: Session, task_id: int, table, people: list[dict[str, str]]):
    db.execute(table.delete().where(table.c.task_id == task_id))
    if not people:
        return
    db.execute(
        table.insert(),
        [
            {
                "task_id": task_id,
                "user_email": person["email"],
                "user_fullname_snapshot": person["fullname"],
            }
            for person in people
        ],
    )


def _clear_task_people(db: Session, task_id: int):
    for table in (task_visible_user, task_execute_user, task_notify_user):
        db.execute(table.delete().where(table.c.task_id == task_id))


def _get_task_people(db: Session, task_id: int, table) -> list[dict[str, str]]:
    rows = db.execute(
        table.select()
        .where(table.c.task_id == task_id)
        .order_by(table.c.user_fullname_snapshot.asc(), table.c.user_email.asc())
    ).mappings().all()
    report_users = get_report_user_map()
    people: list[dict[str, str]] = []
    for row in rows:
        email = normalize_email(row["user_email"])
        report_user = report_users.get(email)
        fullname = report_user.fullname if report_user else (row["user_fullname_snapshot"] or email)
        people.append({"email": email, "fullname": fullname, "display": _format_person(fullname, email)})
    return people


def _get_task_person_emails(db: Session, task_id: int, table) -> set[str]:
    return {person["email"] for person in _get_task_people(db, task_id, table)}


def _format_person(fullname: str, email: str) -> str:
    return f"{fullname}（{email}）" if fullname and fullname != email else email


def _user_email(user: CurrentUser | User) -> str | None:
    if isinstance(user, CurrentUser):
        return normalize_email(user.email) or None
    return normalize_email(user.username) or None


def _validate_execution_window_cron(expression: str | None) -> str | None:
    try:
        return validate_cron_expression(expression)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _task_visible_to_user(db: Session, task: TaskDefinition, user: CurrentUser | User) -> bool:
    if user.has_role("ADMIN"):
        return True
    email = _user_email(user)
    if not email:
        return False
    visible_user_emails = _get_task_person_emails(db, task.id, task_visible_user)
    executable_user_emails = _get_task_person_emails(db, task.id, task_execute_user)
    return email in visible_user_emails or email in executable_user_emails


def _task_executable_by_user(db: Session, task: TaskDefinition, user: CurrentUser | User) -> bool:
    if user.has_role("ADMIN"):
        return True
    email = _user_email(user)
    return bool(email and email in _get_task_person_emails(db, task.id, task_execute_user) and _task_in_execution_window(task))


def _task_in_execution_window(task: TaskDefinition) -> bool:
    return cron_matches_now(task.execution_window_cron)


def _to_admin_schema(db: Session, item: TaskDefinition) -> AdminTaskRead:
    schema = AdminTaskRead.model_validate(item)
    schema.directory_name = item.directory.directory_name if item.directory else None
    schema.directory_path = _build_directory_path(item.directory) if item.directory else None
    schema.visible_user_emails = [person["email"] for person in _get_task_people(db, item.id, task_visible_user)]
    schema.executable_user_emails = [person["email"] for person in _get_task_people(db, item.id, task_execute_user)]
    schema.notify_user_emails = [person["email"] for person in _get_task_people(db, item.id, task_notify_user)]
    return schema


def _to_admin_list_item(item: TaskDefinition) -> AdminTaskListItem:
    schema = AdminTaskListItem.model_validate(item)
    schema.directory_name = item.directory.directory_name if item.directory else None
    schema.directory_path = _build_directory_path(item.directory) if item.directory else None
    return schema


def _to_directory_schema(item: TaskDirectory) -> TaskDirectoryRead:
    return TaskDirectoryRead(
        id=item.id,
        parentDirectoryId=item.parent_id,
        directoryName=item.directory_name,
        directoryPath=_build_directory_path(item),
        level=_get_directory_level(item),
        sortOrder=item.sort_order,
    )


def _sort_directories_as_tree(directories: list[TaskDirectory]) -> list[TaskDirectory]:
    directory_ids = {item.id for item in directories}
    children_by_parent: dict[int | None, list[TaskDirectory]] = {}
    for item in directories:
        parent_id = item.parent_id if item.parent_id in directory_ids else None
        children_by_parent.setdefault(parent_id, []).append(item)
    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.sort_order, item.id))

    ordered: list[TaskDirectory] = []

    def visit(parent_id: int | None):
        for item in children_by_parent.get(parent_id, []):
            ordered.append(item)
            visit(item.id)

    visit(None)
    return ordered


def _collect_directory_ids(db: Session, directory_id: int) -> list[int]:
    ids = [directory_id]
    children = db.query(TaskDirectory).filter(TaskDirectory.parent_id == directory_id).all()
    for child in children:
        ids.extend(_collect_directory_ids(db, child.id))
    return ids


def _build_directory_path(directory: TaskDirectory) -> str:
    names: list[str] = []
    current: TaskDirectory | None = directory
    while current:
        names.append(current.directory_name)
        current = current.parent
    return " / ".join(reversed(names))


def _get_directory_level(directory: TaskDirectory) -> int:
    level = 2
    current = directory.parent
    while current:
        level += 1
        current = current.parent
    return level
