from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BusinessTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    directory_id: int | None = Field(default=None, alias="directoryId")
    directory_name: str | None = Field(default=None, alias="directoryName")
    directory_path: str | None = Field(default=None, alias="directoryPath")
    task_code: str
    display_name: str
    description: str | None = None
    scenario: str | None = None
    prerequisite: str | None = None
    impact_scope: str | None = Field(default=None, alias="impactScope")
    failure_contact: str | None = Field(default=None, alias="failureContact")
    engine_type: str = Field(alias="engineType")
    execution_window_cron: str | None = Field(default=None, alias="executionWindowCron")
    can_execute: bool = Field(default=False, alias="canExecute")
    executable_user_names: list[str] = Field(default_factory=list, alias="executableUserNames")
    executable_user_emails: list[str] = Field(default_factory=list, alias="executableUserEmails")


class TaskUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    directory_id: int | None = Field(default=None, alias="directoryId")
    task_code: str = Field(alias="taskCode")
    display_name: str = Field(alias="displayName")
    description: str | None = None
    scenario: str | None = None
    prerequisite: str | None = None
    impact_scope: str | None = Field(default=None, alias="impactScope")
    failure_contact: str | None = Field(default=None, alias="failureContact")
    engine_type: str = Field(alias="engineType")
    engine_target: str = Field(alias="engineTarget")
    ds_callback_method: str | None = Field(default=None, alias="dsCallbackMethod")
    pg_callback_method: str | None = Field(default=None, alias="pgCallbackMethod")
    parameter_template: dict = Field(default_factory=dict, alias="parameterTemplate")
    repeat_window_minutes: int | None = Field(default=None, alias="repeatWindowMinutes")
    execution_window_cron: str | None = Field(default=None, alias="executionWindowCron")
    published: bool = True
    visible_user_emails: list[str] = Field(default_factory=list, alias="visibleUserEmails")
    executable_user_emails: list[str] = Field(default_factory=list, alias="executableUserEmails")
    notify_user_emails: list[str] = Field(default_factory=list, alias="notifyUserEmails")


class AdminTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    directory_id: int | None = Field(default=None, alias="directoryId")
    directory_name: str | None = Field(default=None, alias="directoryName")
    directory_path: str | None = Field(default=None, alias="directoryPath")
    task_code: str = Field(alias="taskCode")
    display_name: str = Field(alias="displayName")
    description: str | None = None
    scenario: str | None = None
    prerequisite: str | None = None
    impact_scope: str | None = Field(default=None, alias="impactScope")
    failure_contact: str | None = Field(default=None, alias="failureContact")
    engine_type: str = Field(alias="engineType")
    engine_target: str = Field(alias="engineTarget")
    ds_callback_method: str | None = Field(default=None, alias="dsCallbackMethod")
    pg_callback_method: str | None = Field(default=None, alias="pgCallbackMethod")
    parameter_template: dict = Field(alias="parameterTemplate")
    repeat_window_minutes: int | None = Field(default=None, alias="repeatWindowMinutes")
    execution_window_cron: str | None = Field(default=None, alias="executionWindowCron")
    published: bool
    in_task_center: bool = Field(alias="inTaskCenter")
    visible_user_emails: list[str] = Field(default_factory=list, alias="visibleUserEmails")
    executable_user_emails: list[str] = Field(default_factory=list, alias="executableUserEmails")
    notify_user_emails: list[str] = Field(default_factory=list, alias="notifyUserEmails")
    last_test_success: bool | None = Field(default=None, alias="lastTestSuccess")
    last_test_message: str | None = Field(default=None, alias="lastTestMessage")
    last_test_state: str | None = Field(default=None, alias="lastTestState")
    last_tested_at: datetime | None = Field(default=None, alias="lastTestedAt")
    last_test_workflow_summary: dict | None = Field(default=None, alias="lastTestWorkflowSummary")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AdminTaskListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    directory_id: int | None = Field(default=None, alias="directoryId")
    directory_name: str | None = Field(default=None, alias="directoryName")
    directory_path: str | None = Field(default=None, alias="directoryPath")
    task_code: str = Field(alias="taskCode")
    display_name: str = Field(alias="displayName")
    engine_type: str = Field(alias="engineType")
    published: bool
    in_task_center: bool = Field(alias="inTaskCenter")
    last_test_success: bool | None = Field(default=None, alias="lastTestSuccess")


class AdminTaskPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AdminTaskListItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class WorkflowTestSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    process_instance_id: int | None = Field(default=None, alias="processInstanceId")
    process_instance_name: str | None = Field(default=None, alias="processInstanceName")
    process_instance_state: str | int | None = Field(default=None, alias="processInstanceState")
    process_definition_code: str | int | None = Field(default=None, alias="processDefinitionCode")
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    host: str | None = None
    executor_id: int | None = Field(default=None, alias="executorId")
    executor_name: str | None = Field(default=None, alias="executorName")


class TaskExecutionTestResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    message: str
    state: str | int | None = None
    task: AdminTaskRead | None = None
    workflow_summary: WorkflowTestSummary | None = Field(default=None, alias="workflowSummary")


class TaskDirectoryCreate(BaseModel):
    directory_name: str = Field(alias="directoryName")
    parent_id: int | None = Field(default=None, alias="parentDirectoryId")


class TaskDirectoryUpdate(BaseModel):
    directory_name: str = Field(alias="directoryName")


class TaskDirectoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    parent_id: int | None = Field(default=None, alias="parentDirectoryId")
    directory_name: str = Field(alias="directoryName")
    directory_path: str = Field(alias="directoryPath")
    level: int
    sort_order: int = Field(alias="sortOrder")
