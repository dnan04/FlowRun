from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter()


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return get_dashboard_summary(db, user)
