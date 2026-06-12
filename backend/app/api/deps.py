from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.api.current_user import CurrentUser, current_user_from_admin, current_user_from_report
from app.db.session import SessionLocal
from app.models.user import User
from app.services.report_user_service import find_report_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> CurrentUser:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效登录状态")

    if str(subject).startswith("admin:"):
        user_id = str(subject).split(":", 1)[1]
        user = db.get(User, int(user_id))
        if not user or not user.enabled:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
        return current_user_from_admin(user)

    if str(subject).startswith("user:"):
        email = str(subject).split(":", 1)[1]
        report_user = find_report_user(email)
        if not report_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
        return current_user_from_report(report_user)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.has_role("ADMIN"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
    return user
