"""Integration tests for MCP server tools.

Tests the tool functions directly (not via MCP transport).
Uses mocked HTTP for external API calls.
"""

import json
import os

import pytest
import yaml


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")


@pytest.fixture
def clients_file(tmp_path):
    path = tmp_path / "clients.yaml"
    path.write_text(yaml.dump({
        "fixed_clients": [
            {"name": "IDERA", "issue_key": "DELIVERY-1223"},
            {"name": "Magic Memories", "issue_key": "DELIVERY-1310"},
        ]
    }))
    return path


@pytest.fixture
def descriptions_file(tmp_path):
    path = tmp_path / "descriptions.yaml"
    path.write_text(yaml.dump({
        "potential": ["Pre-sales alignment"],
        "fixed": ["Delivery management"],
    }))
    return path


class TestGetFixedClients:
    def test_returns_clients_with_resolved_ids(self, clients_file, httpx_mock):
        from src.server import _get_fixed_clients

        httpx_mock.add_response(
            url="https://test.atlassian.net/rest/api/3/issue/DELIVERY-1223",
            json={"id": "98698", "key": "DELIVERY-1223"},
        )
        httpx_mock.add_response(
            url="https://test.atlassian.net/rest/api/3/issue/DELIVERY-1310",
            json={"id": "95488", "key": "DELIVERY-1310"},
        )

        result = _get_fixed_clients(clients_file)
        assert len(result) == 2
        assert result[0]["issue_id"] == 98698
        assert result[1]["issue_id"] == 95488


class TestPreviewTimesheet:
    def test_preview_returns_summary_and_worklogs(
        self, clients_file, descriptions_file, httpx_mock
    ):
        from src.server import _preview_timesheet

        httpx_mock.add_response(
            url="https://test.atlassian.net/rest/api/3/issue/DELIVERY-1223",
            json={"id": "98698", "key": "DELIVERY-1223"},
        )
        httpx_mock.add_response(
            url="https://test.atlassian.net/rest/api/3/issue/DELIVERY-1310",
            json={"id": "95488", "key": "DELIVERY-1310"},
        )

        result = _preview_timesheet(
            month=4,
            year=2026,
            pto_days=[],
            potentials=[],
            clients_path=clients_file,
            descriptions_path=descriptions_file,
        )
        data = json.loads(result)

        assert data["summary"]["working_days"] == 22
        assert data["summary"]["total_hours"] == 176.0
        assert len(data["worklogs"]) > 0
