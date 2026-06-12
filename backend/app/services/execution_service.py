from datetime import datetime, timedelta

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.current_user import CurrentUser
from app.models.execution import TaskExecution
from app.models.task import TaskDefinition, task_execute_user, task_visible_user
from app.models.user import User
from app.schemas.execution import ExecutionCreate, ExecutionRecordRead
from app.services.audit_service import write_audit_log
from app.services.cron_window import cron_matches_now
from app.services.dolphinscheduler_service import build_execution_request_parameters, execute_ds_task
from app.services.postgres_service import execute_pg_task_with_job_instance_name
from app.services.report_user_service import normalize_email


def get_my_executions(db: Session, user: CurrentUser | User) -> list[ExecutionRecordRead]:
    query = db.query(TaskExecution).options(selectinload(TaskExecution.task), selectinload(TaskExecution.requester))
    if user.has_role("ADMIN"):
        if getattr(user, "id", None) is not None:
            query = query.filter(TaskExecution.requested_by == user.id)
    else:
        query = query.filter(TaskExecution.requested_by_email == _user_email(user))
    executions = (
        query
        .order_by(TaskExecution.requested_at.desc())
        .all()
    )
    return [_to_execution_schema(item) for item in executions]


def get_task_executions(db: Session, user: CurrentUser | User, task_id: int) -> list[ExecutionRecordRead]:
    task = (
        db.query(TaskDefinition)
        .filter(
            TaskDefinition.id == task_id,
            TaskDefinition.published.is_(True),
            TaskDefinition.in_task_center.is_(True),
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    email = _user_email(user)
    visible_user_emails = _get_task_person_emails(db, task.id, task_visible_user)
    executable_user_emails = _get_task_person_emails(db, task.id, task_execute_user)
    if not user.has_role("ADMIN") and (not email or email not in visible_user_emails and email not in executable_user_emails):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前用户无查看权限")

    executions = (
        db.query(TaskExecution)
        .options(selectinload(TaskExecution.task), selectinload(TaskExecution.requester))
        .filter(TaskExecution.task_id == task_id)
        .order_by(TaskExecution.requested_at.desc())
        .all()
    )
    return [_to_execution_schema(item) for item in executions]


def get_all_executions(db: Session) -> list[ExecutionRecordRead]:
    executions = (
        db.query(TaskExecution)
        .options(selectinload(TaskExecution.task), selectinload(TaskExecution.requester))
        .order_by(TaskExecution.requested_at.desc())
        .all()
    )
    return [_to_execution_schema(item) for item in executions]


def enqueue_execution(
    db: Session,
    user: CurrentUser | User,
    task_id: int,
    payload: ExecutionCreate,
    background_tasks: BackgroundTasks,
) -> ExecutionRecordRead:
    task = (
        db.query(TaskDefinition)
        .filter(
            TaskDefinition.id == task_id,
            TaskDefinition.published.is_(True),
            TaskDefinition.in_task_center.is_(True),
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    email = _user_email(user)
    if not user.has_role("ADMIN") and (not email or email not in _get_task_person_emails(db, task.id, task_execute_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前用户无执行权限")
    if not user.has_role("ADMIN") and not _task_in_execution_window(task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前任务不在允许执行日期范围内")

    now = datetime.utcnow()
    if task.repeat_window_minutes:
        blocked = (
            db.query(TaskExecution)
            .filter(
                TaskExecution.task_id == task_id,
                TaskExecution.requested_at >= now - timedelta(minutes=task.repeat_window_minutes),
                TaskExecution.execution_status.in_(["PENDING", "RUNNING"]),
            )
            .order_by(TaskExecution.requested_at.desc())
            .first()
        )
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"该任务在 {task.repeat_window_minutes} 分钟内正在等待执行或正在执行，请勿重复触发",
            )

    execution = TaskExecution(
        task_id=task.id,
        requested_by=user.id if user.has_role("ADMIN") else None,
        requested_by_email=_user_email(user),
        requested_by_name=_user_display_name(user),
        engine_type=task.engine_type,
        engine_target=task.engine_target,
        request_parameters=build_execution_request_parameters(task),
        execution_status="PENDING",
        requested_at=now,
    )
    db.add(execution)
    write_audit_log(
        db,
        action_code="TASK_EXECUTE_REQUEST",
        operator_id=user.id if user.has_role("ADMIN") else None,
        operator_email=None if user.has_role("ADMIN") else _user_email(user),
        operator_name=None if user.has_role("ADMIN") else _user_display_name(user),
        detail=f"用户 {user.username} 发起任务 {task.display_name} 执行。",
    )
    db.commit()
    db.refresh(execution)
    background_tasks.add_task(run_execution_job, execution.id)
    return _to_execution_schema(execution)


def run_execution_job(execution_id: int):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        execution = (
            db.query(TaskExecution)
            .options(selectinload(TaskExecution.task), selectinload(TaskExecution.requester))
            .filter(TaskExecution.id == execution_id)
            .first()
        )
        if not execution:
            return

        execution.execution_status = "RUNNING"
        execution.started_at = datetime.utcnow()
        db.commit()

        if execution.engine_type == "DS":
            external_instance_id, result_summary = execute_ds_task(db, execution, execution.task)
            execution.external_instance_id = external_instance_id
            execution.result_summary = result_summary
        else:
            job_instance_name, result_summary = execute_pg_task_with_job_instance_name(
                execution.engine_target,
                task_name=execution.task.display_name,
                callback_method=execution.task.pg_callback_method,
            )
            execution.external_instance_id = job_instance_name
            execution.result_summary = result_summary

        execution.execution_status = "SUCCEEDED"
        execution.finished_at = datetime.utcnow()
        write_audit_log(
            db,
            action_code="TASK_EXECUTE_FINISHED",
            operator_id=execution.requested_by,
            operator_email=execution.requested_by_email if execution.requested_by is None else None,
            operator_name=execution.requested_by_name if execution.requested_by is None else None,
            detail=f"任务 {execution.task.display_name} 执行成功，实例号 {execution.external_instance_id}。",
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        execution = db.get(TaskExecution, execution_id)
        if execution:
            execution.external_instance_id = execution.external_instance_id or _make_external_instance_id(execution)
            execution.execution_status = "FAILED"
            execution.finished_at = datetime.utcnow()
            execution.error_summary = str(exc)
            db.commit()
    finally:
        db.close()


def _make_external_instance_id(execution: TaskExecution) -> str:
    prefix = "ds" if execution.engine_type == "DS" else "pg"
    return f"{prefix}-{execution.id:06d}"


def _task_in_execution_window(task: TaskDefinition) -> bool:
    return cron_matches_now(task.execution_window_cron)


def _get_task_person_emails(db: Session, task_id: int, table) -> set[str]:
    rows = db.execute(table.select().where(table.c.task_id == task_id)).mappings().all()
    return {normalize_email(row["user_email"]) for row in rows if normalize_email(row["user_email"])}


def _user_email(user: CurrentUser | User) -> str | None:
    if isinstance(user, CurrentUser):
        return normalize_email(user.email) or None
    return normalize_email(user.username) or None


def _user_display_name(user: CurrentUser | User) -> str:
    if isinstance(user, CurrentUser):
        return user.fullname or user.email or user.username
    return user.username


def _to_execution_schema(item: TaskExecution) -> ExecutionRecordRead:
    schema = ExecutionRecordRead.model_validate(item)
    if item.task:
        schema.task_name = item.task.display_name
    if item.requested_by_name:
        schema.requested_by_name = item.requested_by_name
    elif item.requester:
        schema.requested_by_name = item.requester.username
    return schema
