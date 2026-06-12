from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.schema import config_schema, config_table_ref

task_visible_user = Table(
    "dr_task_visible_user",
    Base.metadata,
    Column("task_id", ForeignKey(f"{config_table_ref('dr_task_definition')}.id"), primary_key=True),
    Column("user_email", String(255), primary_key=True),
    Column("user_fullname_snapshot", String(128)),
    schema=config_schema(),
)

task_execute_user = Table(
    "dr_task_execute_user",
    Base.metadata,
    Column("task_id", ForeignKey(f"{config_table_ref('dr_task_definition')}.id"), primary_key=True),
    Column("user_email", String(255), primary_key=True),
    Column("user_fullname_snapshot", String(128)),
    schema=config_schema(),
)

task_notify_user = Table(
    "dr_task_notify_user",
    Base.metadata,
    Column("task_id", ForeignKey(f"{config_table_ref('dr_task_definition')}.id"), primary_key=True),
    Column("user_email", String(255), primary_key=True),
    Column("user_fullname_snapshot", String(128)),
    schema=config_schema(),
)


class TaskDefinition(Base):
    __tablename__ = "dr_task_definition"
    __table_args__ = {"schema": config_schema()}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    directory_id: Mapped[int | None] = mapped_column(ForeignKey(f"{config_table_ref('dr_task_directory')}.id"), nullable=True)
    task_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    prerequisite: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_contact: Mapped[str | None] = mapped_column(String(128), nullable=True)
    engine_type: Mapped[str] = mapped_column(String(16), nullable=False)
    engine_target: Mapped[str] = mapped_column(String(128), nullable=False)
    ds_callback_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    pg_callback_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameter_template: Mapped[dict] = mapped_column(JSON, default=dict)
    repeat_window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_window_cron: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    in_task_center: Mapped[bool] = mapped_column(Boolean, default=False)
    last_test_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_test_workflow_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    directory = relationship("TaskDirectory")


class TaskDirectory(Base):
    __tablename__ = "dr_task_directory"
    __table_args__ = {"schema": config_schema()}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey(f"{config_table_ref('dr_task_directory')}.id"), nullable=True)
    directory_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("TaskDirectory", remote_side=[id], back_populates="children")
    children = relationship("TaskDirectory", back_populates="parent")
