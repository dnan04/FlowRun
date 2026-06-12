from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas.ds import DSConfigRead, DSMetadataOptionsRead
from app.schemas.execution import ExecutionRecordRead
from app.schemas.task import AdminTaskRead, TaskDirectoryCreate, TaskDirectoryRead, TaskDirectoryUpdate, TaskExecutionTestResult, TaskUpsert
from app.schemas.user import SimpleUserRead
from app.services.dolphinscheduler_service import get_ds_config, get_ds_metadata_options
from app.services.execution_service import get_all_executions
from app.services.task_service import (
    add_task_to_center,
    create_task_directory,
    delete_task,
    delete_task_directory,
    list_all_tasks,
    list_task_directories,
    remove_task_from_center,
    test_task_configuration,
    update_task_directory,
    upsert_task,
)
from app.services.user_service import list_users

router = APIRouter()


@router.get("/tasks", response_model=list[AdminTaskRead])
def admin_list_tasks(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return list_all_tasks(db)


@router.get("/task-directories", response_model=list[TaskDirectoryRead])
def admin_list_task_directories(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return list_task_directories(db)


@router.post("/task-directories", response_model=TaskDirectoryRead)
def admin_create_task_directory(
    payload: TaskDirectoryCreate,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return create_task_directory(db, payload, operator)


@router.put("/task-directories/{directory_id}", response_model=TaskDirectoryRead)
def admin_update_task_directory(
    directory_id: int,
    payload: TaskDirectoryUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return update_task_directory(db, directory_id, payload, operator)


@router.delete("/task-directories/{directory_id}")
def admin_delete_task_directory(
    directory_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return delete_task_directory(db, directory_id, operator)


@router.post("/tasks", response_model=AdminTaskRead)
def admin_upsert_task(
    payload: TaskUpsert,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return upsert_task(db, payload, operator)


@router.delete("/tasks/{task_id}")
def admin_delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return delete_task(db, task_id, operator)


@router.post("/tasks/{task_id}/add-to-center", response_model=AdminTaskRead)
def admin_add_task_to_center(
    task_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return add_task_to_center(db, task_id, operator)


@router.post("/tasks/{task_id}/remove-from-center", response_model=AdminTaskRead)
def admin_remove_task_from_center(
    task_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return remove_task_from_center(db, task_id, operator)


@router.post("/tasks/test-execution", response_model=TaskExecutionTestResult)
def admin_test_task_execution(
    payload: TaskUpsert,
    db: Session = Depends(get_db),
    operator: User = Depends(require_admin),
):
    return test_task_configuration(db, payload, operator)


@router.get("/executions", response_model=list[ExecutionRecordRead])
def admin_list_executions(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return get_all_executions(db)


@router.get("/users", response_model=list[SimpleUserRead])
def admin_list_users(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return list_users(db)


@router.get("/ds-config", response_model=DSConfigRead)
def admin_get_ds_config(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return get_ds_config(db)


@router.get("/ds-options", response_model=DSMetadataOptionsRead)
def admin_get_ds_options(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    return get_ds_metadata_options(db)
