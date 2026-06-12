from dataclasses import dataclass

from app.models.user import User
from app.services.report_user_service import ReportUser


@dataclass
class CurrentUser:
    id: int | None
    username: str
    email: str | None
    fullname: str | None
    enabled: bool
    roles: list[str]

    def has_role(self, role_code: str) -> bool:
        return role_code in self.roles


def current_user_from_admin(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        username=user.username,
        email=None,
        fullname=user.username,
        enabled=user.enabled,
        roles=["ADMIN"],
    )


def current_user_from_report(user: ReportUser) -> CurrentUser:
    return CurrentUser(
        id=None,
        username=user.username,
        email=user.email,
        fullname=user.fullname,
        enabled=True,
        roles=[],
    )
