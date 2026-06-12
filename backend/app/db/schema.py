from app.core.config import settings


def config_schema() -> str:
    return settings.platform_config_schema.strip()


def record_schema() -> str:
    return settings.platform_record_schema.strip()


def table_ref(table_name: str, schema_name: str) -> str:
    return f"{schema_name}.{table_name}"


def config_table_ref(table_name: str) -> str:
    return table_ref(table_name, config_schema())


def record_table_ref(table_name: str) -> str:
    return table_ref(table_name, record_schema())
