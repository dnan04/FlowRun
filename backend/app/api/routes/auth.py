from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.current_user import CurrentUser, current_user_from_admin, current_user_from_report
from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.services.report_user_service import find_report_user

router = APIRouter()


def _build_user_profile(user: CurrentUser) -> UserProfile:
    return UserProfile(
        id=user.id or 0,
        username=user.username,
        email=user.email,
        fullname=user.fullname,
        enabled=user.enabled,
        roles=user.roles,
    )


def _get_or_create_login_user(db: Session, username: str) -> tuple[CurrentUser, str]:
    report_user = find_report_user(username)
    if report_user:
        return current_user_from_report(report_user), f"user:{report_user.email}"

    existing_user = db.query(User).filter(User.username == username).first()
    is_admin = username == "finereport_manage" or existing_user is not None
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前用户不在可登录人员视图中")

    user = existing_user
    if not user:
        user = User(
            username=username,
            enabled=True,
        )
        db.add(user)
        db.flush()
        return current_user_from_admin(user), f"admin:{user.id}"

    user.enabled = True
    db.flush()
    return current_user_from_admin(user), f"admin:{user.id}"


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="用户名不能为空")

    user, subject = _get_or_create_login_user(db, username)
    db.commit()
    profile = _build_user_profile(user)
    token = create_access_token(subject)
    return LoginResponse(access_token=token, user=profile)


@router.get("/me", response_model=UserProfile)
def me(user: CurrentUser = Depends(get_current_user)):
    return _build_user_profile(user)
