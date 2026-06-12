from sqlalchemy.orm import Session

from app.schemas.user import SimpleUserRead
from app.services.report_user_service import list_report_user_options


def list_users(db: Session) -> list[SimpleUserRead]:
    return list_report_user_options()
