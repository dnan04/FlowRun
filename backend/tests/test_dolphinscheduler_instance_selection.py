from datetime import datetime
import unittest
from unittest.mock import patch

from app.services.dolphinscheduler_service import DolphinSchedulerTokenClient


class FakeDolphinSchedulerClient(DolphinSchedulerTokenClient):
    def __init__(self, instances, detail_results=None, current_user=None):
        super().__init__("http://example.test", "token")
        self.instances = instances
        self.detail_results = list(detail_results or [])
        self.current_user = current_user

    def query_process_instance_list(self, *args, **kwargs):
        return {"code": 0, "data": {"totalList": self.instances}}

    def query_process_instance_by_id(self, *args, **kwargs):
        if self.detail_results:
            return {"code": 0, "data": self.detail_results.pop(0)}
        return {"code": 0, "data": self.instances[-1]}

    def query_current_user(self):
        return self.current_user


class DolphinSchedulerInstanceSelectionTest(unittest.TestCase):
    def test_selects_instance_started_after_current_launch_from_name_timestamp(self):
        client = FakeDolphinSchedulerClient(
            [
                {
                    "id": 101,
                    "name": "API_test-7-20260502151728957",
                    "processDefinitionCode": "7",
                    "executorId": 1,
                },
                {
                    "id": 102,
                    "name": "API_test-7-20260502151829541",
                    "processDefinitionCode": "7",
                    "executorId": 1,
                },
            ]
        )

        instance = client.find_latest_process_instance(
            project_code="123",
            process_definition_code="7",
            current_user={"id": 1, "username": "admin"},
            launched_after=datetime(2026, 5, 2, 15, 18, 29),
        )

        self.assertEqual(instance["id"], 102)

    def test_waits_until_process_instance_reaches_terminal_state(self):
        client = FakeDolphinSchedulerClient(
            [],
            detail_results=[
                {"id": 102, "name": "API_test-7-20260502151829541", "state": "RUNNING_EXECUTION"},
                {"id": 102, "name": "API_test-7-20260502151829541", "state": "SUCCESS"},
            ],
        )

        instance = client._wait_for_terminal_process_instance(
            project_code="123",
            process_instance_id=102,
            fallback_instance={"id": 102, "state": "RUNNING_EXECUTION"},
            poll_interval_seconds=0,
        )

        self.assertEqual(instance["state"], "SUCCESS")

    def test_none_start_params_are_not_sent_to_ds_start_request(self):
        client = DolphinSchedulerTokenClient("http://example.test", "token")
        captured_urls = []

        def fake_request_json(request):
            captured_urls.append(request.full_url)
            return {"code": 0, "data": {"id": 1}}

        with patch.object(client, "_request_json", side_effect=fake_request_json):
            client.start_process_instance(
                project_code="123",
                process_definition_code="7",
                start_params=None,
            )

        self.assertNotIn("startParams=", captured_urls[0])

    def test_fills_missing_executor_from_current_user(self):
        client = FakeDolphinSchedulerClient(
            [],
            current_user={"id": 9, "username": "admin"},
        )

        enriched = client._ensure_executor_fields({"id": 102, "state": "SUCCESS"})

        self.assertEqual(enriched["executorId"], 9)
        self.assertEqual(enriched["executorName"], "admin")


if __name__ == "__main__":
    unittest.main()
