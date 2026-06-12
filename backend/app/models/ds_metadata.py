from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.schema import config_schema


class DSProject(Base):
    __tablename__ = "ds_project"
    __table_args__ = {"schema": config_schema()}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class DSEnvironment(Base):
    __tablename__ = "ds_environment"
    __table_args__ = {"schema": config_schema()}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class DSAlertGroup(Base):
    __tablename__ = "ds_alertgroup"
    __table_args__ = {"schema": config_schema()}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(128), nullable=False)
    alert_instance_ids: Mapped[str | None] = mapped_column(String(255), nullable=True)
