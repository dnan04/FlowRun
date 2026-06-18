from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.ds_metadata import DSAlertGroup, DSEnvironment, DSProject
from app.models.task import TaskDirectory
from app.models.user import User


def seed_data():
    db = SessionLocal()
    try:
        _seed_task_directories(db)
        _seed_ds_metadata_options(db)
        admin = _seed_users(db)
        if not db.query(AuditLog).filter(AuditLog.action_code == "SYSTEM_INIT").first():
            db.add(
                AuditLog(
                    action_code="SYSTEM_INIT",
                    operator_id=admin.id,
                    detail="初始化系统默认管理员。",
                )
            )
        db.commit()
    finally:
        db.close()


def _seed_task_directories(db: Session):
    pass


def _seed_ds_metadata_options(db: Session):
    pass


def _seed_users(db: Session):
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            enabled=True,
        )
        db.add(admin)
    else:
        admin.enabled = True
    db.flush()
    return admin
