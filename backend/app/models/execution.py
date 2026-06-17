from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.schema import config_table_ref, record_schema


class TaskExecution(Base):
    __tablename__ = "dr_task_execution"
    __table_args__ = {"schema": record_schema()}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey(f"{config_table_ref('dr_task_definition')}.id"), nullable=False)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey(f"{config_table_ref('sys_admin_user')}.id"), nullable=True)
    requested_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    engine_type: Mapped[str] = mapped_column(String(16), nullable=False)
    engine_target: Mapped[str] = mapped_column(Text, nullable=False)
    request_parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    external_instance_id: Mapped[str | None] = mapped_column(String(255))
    result_summary: Mapped[str | None] = mapped_column(Text)
    error_summary: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    task = relationship("TaskDefinition")
    requester = relationship("User")
