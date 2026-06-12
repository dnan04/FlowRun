from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit_log(
    db: Session,
    action_code: str,
    operator_id: int | None,
    detail: str,
    operator_email: str | None = None,
    operator_name: str | None = None,
):
    db.add(
        AuditLog(
            action_code=action_code,
            operator_id=operator_id,
            operator_email=operator_email,
            operator_name=operator_name,
            detail=detail,
        )
    )
