from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DSConfigUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    base_url: str = Field(alias="baseUrl")
    access_token: str | None = Field(default=None, alias="accessToken")
    default_project_code: str | None = Field(default=None, alias="defaultProjectCode")
    worker_group: str = Field(default="default", alias="workerGroup")
    timeout_seconds: int = Field(default=30, alias="timeoutSeconds")
    enabled: bool = True


class DSConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    base_url: str = Field(alias="baseUrl")
    default_project_code: str | None = Field(default=None, alias="defaultProjectCode")
    worker_group: str = Field(alias="workerGroup")
    timeout_seconds: int = Field(alias="timeoutSeconds")
    enabled: bool
    failure_strategy: str = Field(alias="failureStrategy")
    process_instance_priority: str = Field(alias="processInstancePriority")
    warning_type: str = Field(alias="warningType")
    exec_type: str = Field(alias="execType")
    default_environment_code: str | None = Field(default=None, alias="defaultEnvironmentCode")
    default_warning_group_id: str | None = Field(default=None, alias="defaultWarningGroupId")
    default_ds_callback_method: str = Field(alias="defaultDsCallbackMethod")
    default_pg_callback_method: str = Field(alias="defaultPgCallbackMethod")
    token_configured: bool = Field(alias="tokenConfigured")
    last_test_status: str | None = Field(default=None, alias="lastTestStatus")
    last_test_message: str | None = Field(default=None, alias="lastTestMessage")
    last_tested_at: datetime | None = Field(default=None, alias="lastTestedAt")
    updated_at: datetime = Field(alias="updatedAt")


class DSConnectionTestResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    message: str
    code: int | None = None
    tested_at: datetime = Field(alias="testedAt")


class DSProjectOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    code: str


class DSEnvironmentOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    code: str
    name: str


class DSAlertGroupOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    group_name: str = Field(alias="groupName")
    alert_instance_ids: str | None = Field(default=None, alias="alertInstanceIds")


class DSMetadataOptionsRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    projects: list[DSProjectOptionRead]
    environments: list[DSEnvironmentOptionRead]
    warning_groups: list[DSAlertGroupOptionRead] = Field(alias="warningGroups")
