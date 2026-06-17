from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.schema import config_schema, record_schema
from app.db.session import engine


def ensure_database_schemas():
    schema_names = {
        settings.platform_config_schema.strip(),
        settings.platform_record_schema.strip(),
    }
    with engine.begin() as connection:
        for schema_name in schema_names:
            if not schema_name:
                continue
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))


def ensure_runtime_schema():
    inspector = inspect(engine)
    alter_statements: list[str] = []
    schema_name = config_schema()
    record_schema_name = record_schema()
    prefix = f'"{schema_name}".'
    record_prefix = f'"{record_schema_name}".'
    datetime_type = "TIMESTAMP"
    bool_default = "false"

    def table_sql(table_name: str) -> str:
        return f'{prefix}"{table_name}"'

    def record_table_sql(table_name: str) -> str:
        return f'{record_prefix}"{table_name}"'

    tables = set(inspector.get_table_names(schema=schema_name))
    record_tables = set(inspector.get_table_names(schema=record_schema_name))

    if "sys_admin_user" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("sys_admin_user", schema=schema_name)}
        if "id" not in user_columns:
            sequence_name = f'"{schema_name}"."sys_admin_user_id_seq"'
            alter_statements.extend(
                [
                    f"ALTER TABLE {table_sql('sys_admin_user')} ADD COLUMN id INTEGER",
                    f"CREATE SEQUENCE IF NOT EXISTS {sequence_name}",
                    f"UPDATE {table_sql('sys_admin_user')} SET id = nextval('{schema_name}.sys_admin_user_id_seq') WHERE id IS NULL",
                    f"ALTER TABLE {table_sql('sys_admin_user')} ALTER COLUMN id SET DEFAULT nextval('{schema_name}.sys_admin_user_id_seq')",
                    f"ALTER TABLE {table_sql('sys_admin_user')} ALTER COLUMN id SET NOT NULL",
                    f"ALTER TABLE {table_sql('sys_admin_user')} ADD PRIMARY KEY (id)",
                ]
            )
        if "enabled" not in user_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('sys_admin_user')} ADD COLUMN enabled BOOLEAN DEFAULT true NOT NULL"
            )
        if "created_at" not in user_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('sys_admin_user')} ADD COLUMN created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP NOT NULL"
            )
        if "updated_at" not in user_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('sys_admin_user')} ADD COLUMN updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP NOT NULL"
            )
    if "dr_task_definition" in tables:
        raw_task_columns = inspector.get_columns("dr_task_definition", schema=schema_name)
        task_columns = {column["name"] for column in raw_task_columns}
        
        # Check if engine_target needs to be updated to TEXT
        engine_target_col = next((c for c in raw_task_columns if c["name"] == "engine_target"), None)
        if engine_target_col and getattr(engine_target_col["type"], "length", None) is not None:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ALTER COLUMN engine_target TYPE TEXT"
            )

        if "directory_id" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN directory_id INTEGER"
            )
        if "last_test_success" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN last_test_success BOOLEAN"
            )
        if "last_test_message" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN last_test_message TEXT"
            )
        if "last_test_state" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN last_test_state VARCHAR(64)"
            )
        if "last_tested_at" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN last_tested_at {datetime_type}"
            )
        if "last_test_payload_hash" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN last_test_payload_hash VARCHAR(64)"
            )
        if "last_test_workflow_summary" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN last_test_workflow_summary JSON"
            )
        if "in_task_center" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN in_task_center BOOLEAN DEFAULT {bool_default} NOT NULL"
            )
            alter_statements.append(
                f"UPDATE {table_sql('dr_task_definition')} SET in_task_center = 1 WHERE published = 1"
            )
        if "execution_window_cron" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN execution_window_cron VARCHAR(128)"
            )
        if "ds_callback_method" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN ds_callback_method TEXT"
            )
        if "pg_callback_method" not in task_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_definition')} ADD COLUMN pg_callback_method TEXT"
            )

        indexes = inspector.get_indexes("dr_task_definition", schema=schema_name)
        has_display_name_unique = any(
            index.get("unique") and index.get("column_names") == ["display_name"]
            for index in indexes
        )
        if not has_display_name_unique:
            alter_statements.append(
                f"CREATE UNIQUE INDEX IF NOT EXISTS uq_dr_task_definition_display_name "
                f"ON {table_sql('dr_task_definition')} (display_name)"
            )

    for relation_table in ("dr_task_visible_user", "dr_task_execute_user", "dr_task_notify_user"):
        if relation_table in tables:
            relation_columns = {column["name"] for column in inspector.get_columns(relation_table, schema=schema_name)}
            if "user_email" not in relation_columns:
                alter_statements.append(
                    f"ALTER TABLE {table_sql(relation_table)} ADD COLUMN user_email VARCHAR(255)"
                )
            if "user_fullname_snapshot" not in relation_columns:
                alter_statements.append(
                    f"ALTER TABLE {table_sql(relation_table)} ADD COLUMN user_fullname_snapshot VARCHAR(128)"
                )

    if "dr_task_execution" in record_tables:
        raw_execution_columns = inspector.get_columns("dr_task_execution", schema=record_schema_name)
        execution_columns = {column["name"] for column in raw_execution_columns}

        # Check if engine_target needs to be updated to TEXT
        engine_target_col = next((c for c in raw_execution_columns if c["name"] == "engine_target"), None)
        if engine_target_col and getattr(engine_target_col["type"], "length", None) is not None:
            alter_statements.append(
                f"ALTER TABLE {record_table_sql('dr_task_execution')} ALTER COLUMN engine_target TYPE TEXT"
            )

        if "requested_by_email" not in execution_columns:
            alter_statements.append(
                f"ALTER TABLE {record_table_sql('dr_task_execution')} ADD COLUMN requested_by_email VARCHAR(255)"
            )
        if "requested_by_name" not in execution_columns:
            alter_statements.append(
                f"ALTER TABLE {record_table_sql('dr_task_execution')} ADD COLUMN requested_by_name VARCHAR(128)"
            )
        if "requested_by" in execution_columns:
            alter_statements.append(
                f"ALTER TABLE {record_table_sql('dr_task_execution')} ALTER COLUMN requested_by DROP NOT NULL"
            )

    if "dr_audit_log" in record_tables:
        audit_columns = {column["name"] for column in inspector.get_columns("dr_audit_log", schema=record_schema_name)}
        if "operator_email" not in audit_columns:
            alter_statements.append(
                f"ALTER TABLE {record_table_sql('dr_audit_log')} ADD COLUMN operator_email VARCHAR(255)"
            )
        if "operator_name" not in audit_columns:
            alter_statements.append(
                f"ALTER TABLE {record_table_sql('dr_audit_log')} ADD COLUMN operator_name VARCHAR(128)"
            )

    if "dr_task_directory" not in tables:
        return
    else:
        directory_columns = {column["name"] for column in inspector.get_columns("dr_task_directory", schema=schema_name)}
        if "parent_id" not in directory_columns:
            alter_statements.append(
                f"ALTER TABLE {table_sql('dr_task_directory')} ADD COLUMN parent_id INTEGER"
            )

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
