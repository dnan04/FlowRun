import json
from datetime import datetime

from sqlalchemy import create_engine

from app.core.config import settings


def execute_pg_procedure(statement: str) -> str:
    sql_statements = normalize_pg_call_statements(statement)
    pg_url = settings.pg_execution_sqlalchemy_url
    if not pg_url:
        raise RuntimeError(
            "PG 执行数据库未配置，请在 .env 中配置 PG_EXECUTION_HOST、"
            "PG_EXECUTION_DATABASE、PG_EXECUTION_USERNAME 等字段。"
        )

    engine = create_engine(pg_url, pool_pre_ping=True)
    connection = engine.raw_connection()
    try:
        dbapi_connection = getattr(connection, "driver_connection", None) or getattr(
            connection, "connection", connection
        )
        dbapi_connection.autocommit = False
        cursor = dbapi_connection.cursor()
        try:
            for sql in sql_statements:
                cursor.execute(sql)
            dbapi_connection.commit()
        except Exception:
            dbapi_connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()
        engine.dispose()

    return "成功"


def execute_pg_task_with_job_instance_name(
    procedure_statement: str,
    *,
    task_name: str,
    callback_method: str | None = None,
) -> tuple[str, str]:
    job_instance_name = build_job_instance_name(task_name)
    rendered_procedure = render_optional_job_instance_name_argument(procedure_statement, job_instance_name)
    execute_pg_procedure(rendered_procedure)

    if callback_method and callback_method.strip():
        execute_pg_method_with_job_instance_name(callback_method.strip(), job_instance_name)

    return job_instance_name, "成功"


def build_job_instance_name(prefix: str | None = None) -> str:
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S") + f"{now.microsecond // 1000:03d}"
    normalized_prefix = (prefix or "").strip()
    return f"{normalized_prefix}-{timestamp}" if normalized_prefix else timestamp


def execute_pg_method_with_job_instance_name(statement: str, process_instance_name: str | None) -> str:
    if not process_instance_name:
        raise RuntimeError("DS 返回结果缺少 processInstanceName，无法调用后置 PostgreSQL 方法。")
    rendered = render_job_instance_name_argument(statement, process_instance_name)
    return execute_pg_method_expect_empty(rendered)


def render_optional_job_instance_name_argument(statement: str, job_instance_name: str) -> str:
    if ":job_instance_name" not in statement:
        return statement
    return statement.replace(":job_instance_name", _quote_sql_literal(job_instance_name))


def execute_pg_method_expect_empty(statement: str) -> str:
    sql = normalize_pg_method_statement(statement)
    pg_url = settings.pg_execution_sqlalchemy_url
    if not pg_url:
        raise RuntimeError(
            "PG 执行数据库未配置，请在 .env 中配置 PG_EXECUTION_HOST、"
            "PG_EXECUTION_DATABASE、PG_EXECUTION_USERNAME 等字段。"
        )

    engine = create_engine(pg_url, pool_pre_ping=True)
    connection = engine.raw_connection()
    try:
        dbapi_connection = getattr(connection, "driver_connection", None) or getattr(
            connection, "connection", connection
        )
        dbapi_connection.autocommit = False
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall() if cursor.description else []
            columns = [column[0] for column in cursor.description or []]
            dbapi_connection.commit()
        except Exception:
            dbapi_connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()
        engine.dispose()

    if rows:
        raise RuntimeError(f"后置方法返回结果：{_format_query_rows(columns, rows)}")

    return "成功"


def render_job_instance_name_argument(statement: str, process_instance_name: str) -> str:
    if ":job_instance_name" not in statement:
        raise RuntimeError(
            "后置 PostgreSQL 方法必须包含 :job_instance_name 占位符，"
            "例如 SELECT * FROM public.after_ds(:job_instance_name);"
        )
    literal = _quote_sql_literal(process_instance_name)
    return statement.replace(":job_instance_name", literal)


def normalize_pg_method_statement(statement: str) -> str:
    sql = statement.strip()
    if not sql:
        raise RuntimeError("后置 PostgreSQL 方法不能为空。")
    if "；" in sql:
        raise RuntimeError("后置 PostgreSQL 方法只支持英文分号 ;。")
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    if len(statements) != 1:
        raise RuntimeError("后置 PostgreSQL 方法只支持填写一条 SELECT 语句。")
    normalized = statements[0]
    if not normalized.lower().startswith("select "):
        raise RuntimeError(
            "后置 PostgreSQL 方法请填写 SELECT 语句，"
            "例如 SELECT * FROM public.after_ds(:job_instance_name);"
        )
    return f"{normalized};"


def _format_query_rows(columns: list[str], rows) -> str:
    values = []
    for row in rows:
        if columns:
            values.append(dict(zip(columns, row)))
        else:
            values.append(list(row))
    return json.dumps(values, ensure_ascii=False, default=str)


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_pg_call_statements(statement: str) -> list[str]:
    sql = statement.strip()
    if not sql:
        raise RuntimeError("PG 存储过程不能为空。")
    if "；" in sql:
        raise RuntimeError("PG 存储过程多条调用只支持英文分号 ; 分隔。")

    normalized_statements = []
    for item in sql.split(";"):
        normalized = item.strip()
        if not normalized:
            continue
        if not normalized.lower().startswith("call "):
            raise RuntimeError(
                "PG 存储过程请填写 CALL 语句，多条请用英文分号 ; 分隔，"
                "例如 call p_a(); call p_b()。"
            )
        normalized_statements.append(f"{normalized};")

    if not normalized_statements:
        raise RuntimeError("PG 存储过程不能为空。")

    return normalized_statements
