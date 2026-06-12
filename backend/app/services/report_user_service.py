import re
from dataclasses import dataclass

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.schemas.user import SimpleUserRead


@dataclass(frozen=True)
class ReportUser:
    username: str
    fullname: str
    email: str

    @property
    def display_name(self) -> str:
        return f"{self.fullname}（{self.email}）"


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def is_report_user_source_configured() -> bool:
    return bool(settings.report_user_sqlalchemy_url)


def list_report_users(keyword: str | None = None, limit: int | None = None) -> list[ReportUser]:
    if not settings.report_user_sqlalchemy_url:
        return []

    schema_name = _quote_identifier(settings.report_user_schema.strip())
    view_name = _quote_identifier(settings.report_user_view_name.strip())
    relation_name = f"{schema_name}.{view_name}"
    username_column = _quote_identifier(settings.report_user_username_column.strip())
    fullname_column = _quote_identifier(settings.report_user_fullname_column.strip())
    email_column = _quote_identifier(settings.report_user_email_column.strip())
    filters = [
        f"{email_column} IS NOT NULL",
        f"btrim({email_column}) <> ''",
    ]
    params: dict[str, object] = {}
    keyword_text = (keyword or "").strip().lower()
    if keyword_text:
        filters.append(
            "("
            f"lower({username_column}) LIKE :keyword OR "
            f"lower({fullname_column}) LIKE :keyword OR "
            f"lower({email_column}) LIKE :keyword"
            ")"
        )
        params["keyword"] = f"%{keyword_text}%"

    limit_clause = ""
    if limit is not None:
        safe_limit = min(max(limit, 1), 200)
        limit_clause = " LIMIT :limit"
        params["limit"] = safe_limit

    sql = text(
        f"SELECT {username_column} AS username, "
        f"{fullname_column} AS fullname, "
        f"{email_column} AS email "
        f"FROM {relation_name} "
        f"WHERE {' AND '.join(filters)} "
        f"ORDER BY {fullname_column}, {email_column}"
        f"{limit_clause}"
    )
    engine = create_engine(settings.report_user_sqlalchemy_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = connection.execute(sql, params).mappings().all()
    finally:
        engine.dispose()

    seen: set[str] = set()
    users: list[ReportUser] = []
    for row in rows:
        email = normalize_email(str(row["email"] or ""))
        if not email or email in seen:
            continue
        seen.add(email)
        fullname = str(row["fullname"] or "").strip() or email
        username = str(row["username"] or "").strip() or email
        users.append(ReportUser(username=username, fullname=fullname, email=email))
    return users


def list_report_user_options(keyword: str | None = None, limit: int = 50) -> list[SimpleUserRead]:
    return [
        SimpleUserRead(
            id=user.email,
            username=user.username,
            fullname=user.fullname,
            email=user.email,
        )
        for user in list_report_users(keyword=keyword, limit=limit)
    ]


def find_report_user(identity: str) -> ReportUser | None:
    normalized = identity.strip().lower()
    if not normalized:
        return None
    for user in list_report_users():
        if normalized in {user.email.lower(), user.username.lower()}:
            return user
    return None


def get_report_user_map() -> dict[str, ReportUser]:
    return {user.email: user for user in list_report_users()}


def _quote_identifier(value: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise RuntimeError(f"非法的 PostgreSQL 标识符：{value}")
    return f'"{value}"'
