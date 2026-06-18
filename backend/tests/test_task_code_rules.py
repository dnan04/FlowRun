import os
import uuid
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text

schema_suffix = uuid.uuid4().hex[:12]
test_config_schema = f"test_dr_config_{schema_suffix}"
test_record_schema = f"test_dr_record_{schema_suffix}"
os.environ["PLATFORM_CONFIG_SCHEMA"] = test_config_schema
os.environ["PLATFORM_RECORD_SCHEMA"] = test_record_schema


from app.db.base import Base
from app.api.current_user import CurrentUser
import app.models  # noqa: F401
from app.db.runtime_schema import ensure_database_schemas, ensure_runtime_schema
from app.db.seed import seed_data
from app.db.session import SessionLocal, engine
from app.models.audit import AuditLog
from app.models.execution import TaskExecution
from app.models.task import TaskDefinition, TaskDirectory
from app.models.task import task_execute_user, task_notify_user, task_visible_user
from app.models.user import User
from app.schemas.execution import ExecutionCreate
from app.schemas.task import TaskUpsert
from app.schemas.task import WorkflowTestSummary
from app.services.dolphinscheduler_service import build_execution_request_parameters
from app.services.execution_service import enqueue_execution, get_task_executions
from app.services.postgres_service import normalize_pg_call_statements
from app.services.task_service import (
    add_task_to_center,
    delete_task,
    get_visible_tasks,
    list_all_tasks,
    list_visible_task_directories,
    remove_task_from_center,
    upsert_task,
)
from app.services.task_service import test_task_configuration
from app.services.user_service import list_users
from app.schemas.user import SimpleUserRead


class TaskCodeRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_database_schemas()
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema()
        seed_data()

    @classmethod
    def tearDownClass(cls):
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{test_record_schema}" CASCADE'))
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{test_config_schema}" CASCADE'))
        engine.dispose()

    def setUp(self):
        self.db = SessionLocal()
        self.db.query(TaskExecution).delete()
        self.db.execute(task_visible_user.delete())
        self.db.execute(task_execute_user.delete())
        self.db.execute(task_notify_user.delete())
        self.db.query(TaskDefinition).delete()
        for directory in self.db.query(TaskDirectory).order_by(TaskDirectory.id.desc()).all():
            self.db.delete(directory)
        self.db.query(AuditLog).filter(AuditLog.action_code.like("TASK_CONFIG%")).delete()
        self.db.commit()
        self.admin = self.db.query(User).filter(User.username == "admin").one()

    def tearDown(self):
        self.db.close()

    def test_create_delete_and_resequence_task_codes(self):
        first = self._create_pg_task("任务A")
        second = self._create_pg_task("任务B")
        third = self._create_pg_task("任务C")

        self.assertEqual(first.task_code, "1")
        self.assertEqual(second.task_code, "2")
        self.assertEqual(third.task_code, "3")

        execution = TaskExecution(
            task_id=second.id,
            requested_by=self.admin.id,
            engine_type="PG",
            engine_target=second.engine_target,
            request_parameters={},
            execution_status="SUCCEEDED",
        )
        self.db.add(execution)
        self.db.commit()

        delete_task(self.db, second.id, self.admin)

        tasks_after_delete = list_all_tasks(self.db)
        self.assertEqual([task.task_code for task in tasks_after_delete], ["1", "2"])
        self.assertEqual([task.display_name for task in tasks_after_delete], ["任务A", "任务C"])
        self.assertEqual(self.db.query(TaskExecution).filter(TaskExecution.task_id == second.id).count(), 0)

        fourth = self._create_pg_task("任务D")
        self.assertEqual(fourth.task_code, "3")

    def test_task_display_name_must_be_unique(self):
        self._create_pg_task("任务A")

        with self.assertRaises(HTTPException) as context:
            self._create_pg_task("任务A")

        self.assertEqual(context.exception.status_code, 409)

    def test_admin_can_see_published_task_even_when_not_visible_user(self):
        payload = TaskUpsert(
            taskCode="0",
            displayName="仅业务用户可见任务",
            description=None,
            scenario=None,
            prerequisite=None,
            impactScope=None,
            failureContact="",
            engineType="PG",
            engineTarget="call proc_hidden_from_admin()",
            parameterTemplate={},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=True,
        )
        with patch("app.services.task_service.execute_pg_procedure", return_value="ok"):
            test_task_configuration(self.db, payload.model_copy(update={"published": False}), self.admin)
        task = upsert_task(self.db, payload, self.admin)
        add_task_to_center(self.db, task.id, self.admin)

        tasks = get_visible_tasks(self.db, self.admin)
        self.assertEqual([task.display_name for task in tasks], ["仅业务用户可见任务"])

    def test_admin_users_are_hidden_from_people_configuration(self):
        from unittest.mock import patch

        with patch(
            "app.services.user_service.list_report_user_options",
            return_value=[
                SimpleUserRead(id="chen-li@example.com", username="chen-li", email="chen-li@example.com", fullname="陈丽"),
                SimpleUserRead(id="yue-zhao@example.com", username="yue-zhao", email="yue-zhao@example.com", fullname="赵悦"),
                SimpleUserRead(id="gong-chen@example.com", username="gong-chen", email="gong-chen@example.com", fullname="陈工"),
            ],
        ):
            users = list_users(self.db)
        self.assertNotIn("admin", [user.username for user in users])
        self.assertEqual([user.username for user in users], ["chen-li", "yue-zhao", "gong-chen"])

    def test_testing_edited_task_does_not_persist_changes_until_save_or_publish(self):
        task = self._create_pg_task("任务A")
        payload = TaskUpsert(
            taskCode=task.task_code,
            displayName="任务A-编辑未保存",
            description=None,
            scenario=None,
            prerequisite=None,
            impactScope=None,
            failureContact="",
            engineType="DS",
            engineTarget="7",
            parameterTemplate={"projectCode": "123", "workerGroup": "default", "environmentCode": "17337510344640"},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=False,
            id=task.id,
        )

        with patch(
            "app.services.task_service.start_ds_workflow_and_get_summary",
            return_value=(
                WorkflowTestSummary(
                    processInstanceId=50325,
                    processInstanceName="API_test-7-20260502151829541",
                    processInstanceState="SUCCESS",
                    processDefinitionCode="7",
                ),
                "SUCCEEDED",
                "任务A-编辑未保存 执行成功，流程实例 50325 当前状态 SUCCESS。",
            ),
        ):
            result = test_task_configuration(self.db, payload, self.admin)

        self.assertTrue(result.success)
        stored_task = self.db.get(TaskDefinition, task.id)
        self.assertEqual(stored_task.display_name, "任务A")
        self.assertEqual(stored_task.engine_type, "PG")
        self.assertEqual(stored_task.engine_target, "call proc_任务A()")

    def test_contact_and_people_changes_keep_test_and_publish_state(self):
        task_schema = self._create_pg_task("任务A")
        task = self.db.get(TaskDefinition, task_schema.id)
        task.last_test_success = True
        task.last_test_payload_hash = "placeholder"
        self.db.commit()

        original_hash_payload = TaskUpsert(
            taskCode=task.task_code,
            displayName="任务A",
            description=None,
            scenario="测试场景",
            prerequisite="测试前提",
            impactScope="测试范围",
            failureContact="",
            engineType="PG",
            engineTarget="call proc_任务A()",
            parameterTemplate={},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=True,
            id=task.id,
        )
        from app.services import task_service

        task.last_test_payload_hash = task_service._build_task_payload_hash(original_hash_payload)
        self.db.commit()

        changed_people_payload = original_hash_payload.model_copy(
            update={
                "failure_contact": "new-owner",
                "visible_user_emails": [],
                "executable_user_emails": [],
                "published": False,
            }
        )
        upsert_task(self.db, changed_people_payload, self.admin)

        stored_task = self.db.get(TaskDefinition, task.id)
        self.assertTrue(stored_task.published)
        self.assertTrue(stored_task.last_test_success)
        self.assertEqual(stored_task.failure_contact, "new-owner")
        self.assertEqual(self._task_people_count(task_visible_user, task.id), 0)
        self.assertEqual(self._task_people_count(task_execute_user, task.id), 0)

    def test_publish_request_updates_publish_state_when_execution_config_unchanged(self):
        task_schema = self._create_pg_task("任务A")
        task = self.db.get(TaskDefinition, task_schema.id)
        task.published = False
        self.db.commit()

        publish_payload = TaskUpsert(
            taskCode=task.task_code,
            displayName="任务A",
            description=None,
            scenario="测试场景",
            prerequisite="测试前提",
            impactScope="测试范围",
            failureContact="",
            engineType="PG",
            engineTarget="call proc_任务A()",
            parameterTemplate={},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=True,
            id=task.id,
        )

        upsert_task(self.db, publish_payload, self.admin)

        stored_task = self.db.get(TaskDefinition, task.id)
        self.assertTrue(stored_task.published)

    def test_pg_non_execution_changes_keep_test_and_publish_state(self):
        task_schema = self._create_pg_task("任务A")
        task = self.db.get(TaskDefinition, task_schema.id)
        self.assertTrue(task.published)
        self.assertTrue(task.last_test_success)

        changed_payload = TaskUpsert(
            id=task.id,
            taskCode=task.task_code,
            displayName="任务A",
            description=None,
            scenario="测试场景",
            prerequisite="新前提",
            impactScope="新范围",
            failureContact="new-owner",
            engineType="PG",
            engineTarget="call proc_任务A()",
            parameterTemplate={},
            repeatWindowMinutes=60,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=False,
        )
        upsert_task(self.db, changed_payload, self.admin)

        stored_task = self.db.get(TaskDefinition, task.id)
        self.assertTrue(stored_task.published)
        self.assertTrue(stored_task.last_test_success)
        self.assertEqual(stored_task.prerequisite, "新前提")
        self.assertEqual(stored_task.impact_scope, "新范围")
        self.assertEqual(stored_task.repeat_window_minutes, 60)
        self.assertEqual(stored_task.failure_contact, "new-owner")

    def test_pg_execution_change_requires_retest_before_publish(self):
        task_schema = self._create_pg_task("任务A")
        changed_payload = TaskUpsert(
            id=task_schema.id,
            taskCode=task_schema.task_code,
            displayName="任务A",
            description=None,
            scenario="测试场景",
            prerequisite="测试前提",
            impactScope="测试范围",
            failureContact="",
            engineType="PG",
            engineTarget="call proc_任务A_new()",
            parameterTemplate={},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=False,
        )
        upsert_task(self.db, changed_payload, self.admin)
        stored_task = self.db.get(TaskDefinition, task_schema.id)
        self.assertFalse(stored_task.published)
        self.assertIsNone(stored_task.last_test_success)

        with self.assertRaises(HTTPException) as context:
            upsert_task(self.db, changed_payload.model_copy(update={"published": True}), self.admin)
        self.assertEqual(context.exception.status_code, 409)

    def test_pg_allows_multiple_call_statements(self):
        statements = normalize_pg_call_statements("call p_a(); call public.p_b();")
        self.assertEqual(statements, ["call p_a();", "call public.p_b();"])

        payload = TaskUpsert(
            taskCode="0",
            displayName="多存储过程任务",
            description=None,
            scenario=None,
            prerequisite=None,
            impactScope=None,
            failureContact="",
            engineType="PG",
            engineTarget="call p_a(); call public.p_b();",
            parameterTemplate={},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=False,
        )
        with patch("app.services.task_service.execute_pg_procedure", return_value="ok") as mocked_execute:
            result = test_task_configuration(self.db, payload, self.admin)
        self.assertTrue(result.success)
        mocked_execute.assert_called_once_with("call p_a(); call public.p_b();")
        task = upsert_task(self.db, payload, self.admin)
        self.assertEqual(task.engine_target, "call p_a(); call public.p_b();")

    def test_pg_rejects_chinese_semicolon_separator(self):
        with self.assertRaises(RuntimeError):
            normalize_pg_call_statements("call p_a()； call p_b()")

    def test_ds_non_execution_changes_keep_test_and_publish_state(self):
        payload = TaskUpsert(
            taskCode="0",
            displayName="DS任务A",
            description=None,
            scenario=None,
            prerequisite="旧前提",
            impactScope="旧范围",
            failureContact="old-owner",
            engineType="DS",
            engineTarget="7",
            parameterTemplate={
                "projectCode": "123",
                "failureStrategy": "CONTINUE",
                "processInstancePriority": "MEDIUM",
                "warningType": "NONE",
                "workerGroup": "default",
                "execType": "START_PROCESS",
                "startParams": None,
                "environmentCode": "17337510344640",
            },
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=False,
        )
        with patch(
            "app.services.task_service.start_ds_workflow_and_get_summary",
            return_value=(WorkflowTestSummary(processInstanceId=1, processInstanceState="SUCCESS"), "SUCCEEDED", "ok"),
        ):
            result = test_task_configuration(self.db, payload, self.admin)
        self.assertTrue(result.success)

        task_schema = upsert_task(self.db, payload.model_copy(update={"published": True}), self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        self.assertTrue(task.published)
        self.assertTrue(task.last_test_success)

        changed_payload = payload.model_copy(
            update={
                "id": task.id,
                "published": False,
                "prerequisite": "新前提",
                "impact_scope": "新范围",
                "repeat_window_minutes": 60,
                "failure_contact": "new-owner",
                "visible_user_emails": [],
                "executable_user_emails": [],
            }
        )
        upsert_task(self.db, changed_payload, self.admin)

        stored_task = self.db.get(TaskDefinition, task.id)
        self.assertTrue(stored_task.published)
        self.assertTrue(stored_task.last_test_success)
        self.assertEqual(stored_task.prerequisite, "新前提")
        self.assertEqual(stored_task.impact_scope, "新范围")
        self.assertEqual(stored_task.repeat_window_minutes, 60)
        self.assertEqual(stored_task.failure_contact, "new-owner")

    def test_remove_task_from_center_only_removes_task_center_entry(self):
        task_schema = self._create_pg_task("任务A")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        execution = TaskExecution(
            task_id=task.id,
            requested_by=self.admin.id,
            engine_type="PG",
            engine_target=task.engine_target,
            request_parameters={},
            execution_status="SUCCEEDED",
        )
        self.db.add(execution)
        self.db.commit()

        result = remove_task_from_center(self.db, task.id, self.admin)

        stored_task = self.db.get(TaskDefinition, task.id)
        self.assertTrue(result.published)
        self.assertTrue(stored_task.published)
        self.assertFalse(result.in_task_center)
        self.assertFalse(stored_task.in_task_center)
        self.assertEqual(stored_task.display_name, "任务A")
        self.assertEqual(self.db.query(TaskExecution).filter(TaskExecution.task_id == task.id).count(), 1)

    def test_execution_parameters_do_not_auto_inject_business_date(self):
        task_schema = self._create_pg_task("任务A")
        task = self.db.get(TaskDefinition, task_schema.id)
        task.parameter_template = {}
        self.db.commit()

        self.assertEqual(build_execution_request_parameters(task), {})

    def test_visible_user_can_view_task_execution_logs(self):
        business_user = self._business_user("chen-li@example.com", "chen-li")
        task_schema = self._create_pg_task("任务A")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        self._set_task_people(task_visible_user, task.id, [business_user])
        execution = TaskExecution(
            task_id=task.id,
            requested_by=None,
            requested_by_email=business_user.email,
            requested_by_name=business_user.fullname,
            engine_type="PG",
            engine_target=task.engine_target,
            request_parameters={},
            execution_status="SUCCEEDED",
            result_summary="任务A 已完成。",
        )
        self.db.add(execution)
        self.db.commit()

        logs = get_task_executions(self.db, business_user, task.id)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].requested_by_name, "chen-li")
        self.assertEqual(logs[0].execution_status, "SUCCEEDED")

    def test_business_user_sees_visible_or_executable_tasks_with_execute_flag(self):
        visible_user = self._business_user("chen-li@example.com", "chen-li")
        executable_user = self._business_user("yue-zhao@example.com", "yue-zhao")
        outsider = self._business_user("gong-chen@example.com", "gong-chen")

        visible_task_schema = self._create_pg_task("visible_only_task")
        add_task_to_center(self.db, visible_task_schema.id, self.admin)
        visible_task = self.db.get(TaskDefinition, visible_task_schema.id)
        self._set_task_people(task_visible_user, visible_task.id, [visible_user])
        self._set_task_people(task_execute_user, visible_task.id, [])

        executable_task_schema = self._create_pg_task("executable_only_task")
        add_task_to_center(self.db, executable_task_schema.id, self.admin)
        executable_task = self.db.get(TaskDefinition, executable_task_schema.id)
        self._set_task_people(task_visible_user, executable_task.id, [])
        self._set_task_people(task_execute_user, executable_task.id, [executable_user])
        self.db.commit()

        visible_results = get_visible_tasks(self.db, visible_user)
        executable_results = get_visible_tasks(self.db, executable_user)
        outsider_results = get_visible_tasks(self.db, outsider)

        self.assertEqual([task.display_name for task in visible_results], ["visible_only_task"])
        self.assertFalse(visible_results[0].can_execute)
        self.assertEqual([task.display_name for task in executable_results], ["executable_only_task"])
        self.assertTrue(executable_results[0].can_execute)
        self.assertEqual(outsider_results, [])

    def test_executable_user_can_view_task_execution_logs(self):
        business_user = self._business_user("chen-li@example.com", "chen-li")
        task_schema = self._create_pg_task("executable_log_task")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        self._set_task_people(task_visible_user, task.id, [])
        self._set_task_people(task_execute_user, task.id, [business_user])
        execution = TaskExecution(
            task_id=task.id,
            requested_by=None,
            requested_by_email=business_user.email,
            requested_by_name=business_user.fullname,
            engine_type="PG",
            engine_target=task.engine_target,
            request_parameters={},
            execution_status="SUCCEEDED",
            result_summary="done",
        )
        self.db.add(execution)
        self.db.commit()

        logs = get_task_executions(self.db, business_user, task.id)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].requested_by_name, "chen-li")

    def test_business_user_cannot_execute_task_outside_execution_window(self):
        business_user = self._business_user("chen-li@example.com", "chen-li")
        task_schema = self._create_pg_task("window_limited_task")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        self._set_task_people(task_visible_user, task.id, [])
        self._set_task_people(task_execute_user, task.id, [business_user])
        task.execution_window_cron = "0 0 31 2 *"
        self.db.commit()

        tasks = get_visible_tasks(self.db, business_user)

        self.assertEqual([item.display_name for item in tasks], ["window_limited_task"])
        self.assertFalse(tasks[0].can_execute)
        with self.assertRaises(HTTPException) as context:
            enqueue_execution(self.db, business_user, task.id, ExecutionCreate(), BackgroundTasks())
        self.assertEqual(context.exception.status_code, 403)

    def test_repeat_window_blocks_different_users_for_same_task(self):
        first_user = self._business_user("chen-li@example.com", "chen-li")
        second_user = self._business_user("yue-zhao@example.com", "yue-zhao")
        task_schema = self._create_pg_task("repeat_window_task")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        task.repeat_window_minutes = 30
        self._set_task_people(task_visible_user, task.id, [])
        self._set_task_people(task_execute_user, task.id, [first_user, second_user])
        execution = TaskExecution(
            task_id=task.id,
            requested_by=None,
            requested_by_email=first_user.email,
            requested_by_name=first_user.fullname,
            engine_type="PG",
            engine_target=task.engine_target,
            request_parameters={},
            execution_status="RUNNING",
        )
        self.db.add(execution)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            enqueue_execution(self.db, second_user, task.id, ExecutionCreate(), BackgroundTasks())

        self.assertEqual(context.exception.status_code, 409)

    def test_repeat_window_allows_different_user_after_task_succeeds(self):
        first_user = self._business_user("chen-li@example.com", "chen-li")
        second_user = self._business_user("yue-zhao@example.com", "yue-zhao")
        task_schema = self._create_pg_task("repeat_window_succeeded_task")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        task.repeat_window_minutes = 30
        self._set_task_people(task_visible_user, task.id, [])
        self._set_task_people(task_execute_user, task.id, [first_user, second_user])
        execution = TaskExecution(
            task_id=task.id,
            requested_by=None,
            requested_by_email=first_user.email,
            requested_by_name=first_user.fullname,
            engine_type="PG",
            engine_target=task.engine_target,
            request_parameters={},
            execution_status="SUCCEEDED",
        )
        self.db.add(execution)
        self.db.commit()

        result = enqueue_execution(self.db, second_user, task.id, ExecutionCreate(), BackgroundTasks())

        self.assertEqual(result.requested_by_name, "yue-zhao")
        self.assertEqual(result.execution_status, "PENDING")

    def test_repeat_window_allows_pending_task_after_window_expires(self):
        first_user = self._business_user("chen-li@example.com", "chen-li")
        second_user = self._business_user("yue-zhao@example.com", "yue-zhao")
        task_schema = self._create_pg_task("repeat_window_expired_task")
        add_task_to_center(self.db, task_schema.id, self.admin)
        task = self.db.get(TaskDefinition, task_schema.id)
        task.repeat_window_minutes = 30
        self._set_task_people(task_visible_user, task.id, [])
        self._set_task_people(task_execute_user, task.id, [first_user, second_user])
        execution = TaskExecution(
            task_id=task.id,
            requested_by=None,
            requested_by_email=first_user.email,
            requested_by_name=first_user.fullname,
            engine_type="PG",
            engine_target=task.engine_target,
            request_parameters={},
            execution_status="PENDING",
            requested_at=datetime.utcnow() - timedelta(minutes=31),
        )
        self.db.add(execution)
        self.db.commit()

        result = enqueue_execution(self.db, second_user, task.id, ExecutionCreate(), BackgroundTasks())

        self.assertEqual(result.requested_by_name, "yue-zhao")
        self.assertEqual(result.execution_status, "PENDING")

    def test_business_user_only_sees_directories_with_visible_or_executable_tasks(self):
        business_user = self._business_user("chen-li@example.com", "chen-li")
        logistics = TaskDirectory(directory_name="logistics", sort_order=10)
        finance = TaskDirectory(directory_name="finance", sort_order=20)
        supply = TaskDirectory(directory_name="supply", sort_order=30)
        self.db.add_all([logistics, finance, supply])
        self.db.flush()
        finance_asia = TaskDirectory(parent_id=finance.id, directory_name="finance_asia", sort_order=10)
        finance_europe = TaskDirectory(parent_id=finance.id, directory_name="finance_europe", sort_order=20)
        self.db.add_all([finance_asia, finance_europe])
        self.db.commit()

        logistics_task_schema = self._create_pg_task("logistics_task")
        add_task_to_center(self.db, logistics_task_schema.id, self.admin)
        logistics_task = self.db.get(TaskDefinition, logistics_task_schema.id)
        logistics_task.directory_id = logistics.id
        self._set_task_people(task_visible_user, logistics_task.id, [])
        self._set_task_people(task_execute_user, logistics_task.id, [business_user])

        asia_task_schema = self._create_pg_task("finance_asia_task")
        add_task_to_center(self.db, asia_task_schema.id, self.admin)
        asia_task = self.db.get(TaskDefinition, asia_task_schema.id)
        asia_task.directory_id = finance_asia.id
        self._set_task_people(task_visible_user, asia_task.id, [business_user])
        self._set_task_people(task_execute_user, asia_task.id, [])

        supply_task_schema = self._create_pg_task("supply_task")
        add_task_to_center(self.db, supply_task_schema.id, self.admin)
        supply_task = self.db.get(TaskDefinition, supply_task_schema.id)
        supply_task.directory_id = supply.id
        self._set_task_people(task_visible_user, supply_task.id, [])
        self._set_task_people(task_execute_user, supply_task.id, [])
        self.db.commit()

        directories = list_visible_task_directories(self.db, business_user)

        self.assertEqual([directory.directory_name for directory in directories], ["logistics", "finance", "finance_asia"])

    def _create_pg_task(self, display_name: str):
        payload = TaskUpsert(
            taskCode="0",
            displayName=display_name,
            description=None,
            scenario="测试场景",
            prerequisite="测试前提",
            impactScope="测试范围",
            failureContact="",
            engineType="PG",
            engineTarget=f"call proc_{display_name}()",
            parameterTemplate={},
            repeatWindowMinutes=30,
            visibleUserEmails=[],
            executableUserEmails=[],
            notifyUserEmails=[],
            published=False,
        )
        with patch("app.services.task_service.execute_pg_procedure", return_value="ok"):
            result = test_task_configuration(self.db, payload, self.admin)
        self.assertTrue(result.success)
        return upsert_task(self.db, payload.model_copy(update={"published": True}), self.admin)

    def _business_user(self, email: str, fullname: str):
        return CurrentUser(
            id=None,
            username=email,
            email=email,
            fullname=fullname,
            enabled=True,
            roles=[],
        )

    def _set_task_people(self, table, task_id: int, users: list[CurrentUser]):
        self.db.execute(table.delete().where(table.c.task_id == task_id))
        if users:
            self.db.execute(
                table.insert(),
                [
                    {
                        "task_id": task_id,
                        "user_email": user.email,
                        "user_fullname_snapshot": user.fullname,
                    }
                    for user in users
                ],
            )
        self.db.flush()

    def _task_people_count(self, table, task_id: int):
        return len(self.db.execute(table.select().where(table.c.task_id == task_id)).all())


if __name__ == "__main__":
    unittest.main()
