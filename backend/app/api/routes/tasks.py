from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.execution import ExecutionCreate, ExecutionRecordRead
from app.schemas.task import BusinessTaskRead, TaskDirectoryRead
from app.services.execution_service import enqueue_execution, get_my_executions, get_task_executions
from app.services.task_service import get_visible_tasks, list_visible_task_directories

router = APIRouter()


@router.get("/my", response_model=list[BusinessTaskRead])
def list_my_tasks(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return get_visible_tasks(db, user)


@router.get("/directories", response_model=list[TaskDirectoryRead])
def list_directories(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return list_visible_task_directories(db, user)


@router.get("/executions/my", response_model=list[ExecutionRecordRead])
def list_my_executions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return get_my_executions(db, user)


@router.get("/{task_id}/executions", response_model=list[ExecutionRecordRead])
def list_task_executions(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_task_executions(db, user, task_id)


@router.post("/{task_id}/execute", response_model=ExecutionRecordRead)
def execute_task(
    task_id: int,
    payload: ExecutionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return enqueue_execution(db, user, task_id, payload, background_tasks)
