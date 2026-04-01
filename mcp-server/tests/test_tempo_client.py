import httpx
import pytest
import time


class TestCreateWorklog:
    def test_creates_single_worklog(self, httpx_mock):
        from src.tempo_client import TempoClient

        httpx_mock.add_response(
            method="POST",
            url="https://api.tempo.io/4/worklogs",
            json={"tempoWorklogId": 12345},
            status_code=200,
        )

        client = TempoClient("test-token")
        result = client.create_worklog(
            issue_id=114282,
            date="2026-04-15",
            seconds=5400,
            description="Test worklog",
        )

        assert result["tempoWorklogId"] == 12345
        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer test-token"

    def test_submit_batch(self, httpx_mock):
        from src.tempo_client import TempoClient

        for _ in range(3):
            httpx_mock.add_response(
                method="POST",
                url="https://api.tempo.io/4/worklogs",
                json={"tempoWorklogId": 100},
                status_code=200,
            )

        client = TempoClient("test-token")
        worklogs = [
            {"issueId": 1, "timeSpentSeconds": 3600, "startDate": "2026-04-01", "description": "A"},
            {"issueId": 2, "timeSpentSeconds": 3600, "startDate": "2026-04-01", "description": "B"},
            {"issueId": 3, "timeSpentSeconds": 3600, "startDate": "2026-04-01", "description": "C"},
        ]

        result = client.submit_batch(worklogs)
        assert result["submitted"] == 3
        assert result["failed"] == 0
        assert len(result["errors"]) == 0

    def test_submit_batch_handles_failure(self, httpx_mock):
        from src.tempo_client import TempoClient

        httpx_mock.add_response(method="POST", json={"tempoWorklogId": 1}, status_code=200)
        httpx_mock.add_response(method="POST", status_code=500)
        httpx_mock.add_response(method="POST", status_code=500)  # retry also fails

        client = TempoClient("test-token")
        worklogs = [
            {"issueId": 1, "timeSpentSeconds": 3600, "startDate": "2026-04-01", "description": "A"},
            {"issueId": 2, "timeSpentSeconds": 3600, "startDate": "2026-04-01", "description": "B"},
        ]

        result = client.submit_batch(worklogs)
        assert result["submitted"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
