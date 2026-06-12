from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ExecutionRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    task_name: str | None = None
    requested_by_name: str | None = None
    requested_by_email: str | None = None
    engine_type: str
    engine_target: str
    request_parameters: dict
    execution_status: str
    external_instance_id: str | None = None
    result_summary: str | None = None
    error_summary: str | None = None
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
