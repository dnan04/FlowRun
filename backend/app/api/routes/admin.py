from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas.ds import DSConfigRead, DSMetadataOptionsRead
from app.schemas.execution import ExecutionRecordRead
from app.schemas.task import AdminTaskListItem, AdminTaskPage, AdminTaskRead, TaskDirectoryCreate, TaskDirectoryRead, TaskDirectoryUpdate, TaskExecutionTestResult, TaskUpsert
from app.schemas.user import SimpleUserRead
from app.services.dolphinscheduler_service import get_ds_config, get_ds_metadata_options
from app.services.execution_service import get_all_executions
from app.services.task_service import (
    add_task_to_center,
    create_task_directory,
    delete_task,
    delete_task_directory,
    get_admin_task,
    list_all_tasks,
    list_admin_tasks,
    list_available_tasks_for_center,
    list_task_directories,
    remove_task_from_center,
    test_task_configuration,
    update_task_directory,
    upsert_task,
)
from app.services.user_service import list_users

router = APIRouter()


@router.get("/tasks", response_model=AdminTaskPage)
def admin_list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    keyword: str | None = Query(default=None),
    engine_type: str | None = Query(default=None, alias="engineType"),
    directory_id: int | None = Query(default=None, alias="directoryId"),
    uncategorized: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return list_admin_tasks(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        engine_type=engine_type,
        directory_id=directory_id,
        uncategorized=uncategorized,
    )


@router.get("/tasks/available-for-center", response_model=list[AdminTaskListItem])
def admin_list_available_tasks_for_center(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return list_available_tasks_for_center(db, keyword=keyword, limit=limit)


@router.get("/tasks/{task_id}", response_model=AdminTaskRead)
def admin_get_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_admin_task(db, task_id)


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
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return list_users(db, keyword=keyword, limit=limit)


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
