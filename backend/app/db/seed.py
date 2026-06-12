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
    existing_names = {
        item.directory_name for item in db.query(TaskDirectory).all()
    }
    directories = [
        ("物流", 10),
        ("财务", 20),
        ("供应链", 30),
    ]
    for name, sort_order in directories:
        if name not in existing_names:
            db.add(TaskDirectory(directory_name=name, sort_order=sort_order))


def _seed_ds_metadata_options(db: Session):
    if not db.query(DSProject).first():
        db.add_all(
            [
                DSProject(id=1, name="美库PG数仓调度平台", code="17268230837056"),
                DSProject(id=2, name="测试项目", code="17268232252608"),
            ]
        )

    if not db.query(DSEnvironment).first():
        db.add_all(
            [
                DSEnvironment(id=2, code="17337510344640", name="python3.10执行环境"),
                DSEnvironment(id=1, code="17269536643008", name="默认环境"),
            ]
        )

    if not db.query(DSAlertGroup).first():
        db.add_all(
            [
                DSAlertGroup(id=3, group_name="运营数据质量告警", alert_instance_ids="2"),
                DSAlertGroup(id=36, group_name="财务数据质量告警", alert_instance_ids="35"),
                DSAlertGroup(id=37, group_name="美线销售数据person异常告警", alert_instance_ids="36,35"),
                DSAlertGroup(id=2, group_name="工作流调度失败告警", alert_instance_ids="37"),
                DSAlertGroup(id=1, group_name="default admin warning group", alert_instance_ids="2,37"),
            ]
        )


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
