from sqlalchemy.orm import Session

from app.schemas.user import SimpleUserRead
from app.services.report_user_service import list_report_user_options


def list_users(db: Session, keyword: str | None = None, limit: int = 50) -> list[SimpleUserRead]:
    return list_report_user_options(keyword=keyword, limit=limit)
