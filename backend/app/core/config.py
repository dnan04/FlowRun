from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DataRunner Platform"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "replace-with-production-secret"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"
    cors_origins: list[str] = Field(default=["http://localhost:5173"])

    platform_db_host: str = ""
    platform_db_port: int = 5432
    platform_db_database: str = ""
    platform_db_username: str = ""
    platform_db_password: str = ""
    platform_db_sslmode: str = "prefer"
    platform_config_schema: str = "dr_config"
    platform_record_schema: str = "dr_record"

    report_user_db_host: str = ""
    report_user_db_port: int = 5432
    report_user_db_database: str = ""
    report_user_db_username: str = ""
    report_user_db_password: str = ""
    report_user_db_sslmode: str = "prefer"
    report_user_schema: str = "public"
    report_user_view_name: str = "report_department_user_list"
    report_user_username_column: str = "username"
    report_user_fullname_column: str = "fullname"
    report_user_email_column: str = "email"

    pg_execution_host: str = ""
    pg_execution_port: int = 5432
    pg_execution_database: str = ""
    pg_execution_username: str = ""
    pg_execution_password: str = ""
    pg_execution_sslmode: str = "prefer"
    task_default_ds_callback_method: str = "SELECT * FROM public.get_user_rank(:job_instance_name) ;"
    task_default_pg_callback_method: str = "SELECT * FROM public.get_user_rank(:job_instance_name) ;"

    dolphinscheduler_base_url: str = "http://dolphinscheduler.example/api"
    dolphinscheduler_access_token: str = ""
    dolphinscheduler_project_code: str = ""
    dolphinscheduler_tenant_code: str = "default"
    dolphinscheduler_worker_group: str = "default"
    dolphinscheduler_timeout_seconds: int = 30
    dolphinscheduler_enabled: bool = True
    dolphinscheduler_failure_strategy: str = "CONTINUE"
    dolphinscheduler_process_instance_priority: str = "MEDIUM"
    dolphinscheduler_warning_type: str = "NONE"
    dolphinscheduler_exec_type: str = "START_PROCESS"
    dolphinscheduler_environment_code: str = ""
    dolphinscheduler_warning_group_id: str = ""

    @property
    def pg_execution_sqlalchemy_url(self) -> str:
        if not all([
            self.pg_execution_host.strip(),
            self.pg_execution_database.strip(),
            self.pg_execution_username.strip(),
        ]):
            return ""

        username = quote_plus(self.pg_execution_username.strip())
        password = quote_plus(self.pg_execution_password)
        auth = f"{username}:{password}" if password else username
        host = self.pg_execution_host.strip()
        database = quote_plus(self.pg_execution_database.strip())
        url = f"postgresql+psycopg2://{auth}@{host}:{self.pg_execution_port}/{database}"
        if self.pg_execution_sslmode.strip():
            url = f"{url}?sslmode={quote_plus(self.pg_execution_sslmode.strip())}"
        return url

    @property
    def platform_sqlalchemy_url(self) -> str:
        if not all([
            self.platform_db_host.strip(),
            self.platform_db_database.strip(),
            self.platform_db_username.strip(),
        ]):
            return ""

        username = quote_plus(self.platform_db_username.strip())
        password = quote_plus(self.platform_db_password)
        auth = f"{username}:{password}" if password else username
        host = self.platform_db_host.strip()
        database = quote_plus(self.platform_db_database.strip())
        url = f"postgresql+psycopg2://{auth}@{host}:{self.platform_db_port}/{database}"
        if self.platform_db_sslmode.strip():
            url = f"{url}?sslmode={quote_plus(self.platform_db_sslmode.strip())}"
        return url

    @property
    def report_user_sqlalchemy_url(self) -> str:
        if not all([
            self.report_user_db_host.strip(),
            self.report_user_db_database.strip(),
            self.report_user_db_username.strip(),
        ]):
            return ""

        username = quote_plus(self.report_user_db_username.strip())
        password = quote_plus(self.report_user_db_password)
        auth = f"{username}:{password}" if password else username
        host = self.report_user_db_host.strip()
        database = quote_plus(self.report_user_db_database.strip())
        url = f"postgresql+psycopg2://{auth}@{host}:{self.report_user_db_port}/{database}"
        if self.report_user_db_sslmode.strip():
            url = f"{url}?sslmode={quote_plus(self.report_user_db_sslmode.strip())}"
        return url


settings = Settings()
