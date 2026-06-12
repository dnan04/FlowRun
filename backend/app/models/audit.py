from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.schema import config_table_ref, record_schema


class AuditLog(Base):
    __tablename__ = "dr_audit_log"
    __table_args__ = {"schema": record_schema()}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action_code: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey(f"{config_table_ref('sys_admin_user')}.id"))
    operator_email: Mapped[str | None] = mapped_column(String(255))
    operator_name: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
