"""Tests for the CLI (preview and submit subcommands)."""

import json

import pytest


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")


def test_cli_module_imports():
    from src.cli import cmd_preview, cmd_submit, main  # noqa: F401


class TestCLIPreview:
    def test_preview_writes_valid_json_file(self, tmp_path, httpx_mock):
        """preview saves valid JSON with summary + worklogs to --output path."""
        from src.cli import cmd_preview
        import argparse

        output = tmp_path / "preview.json"
        args = argparse.Namespace(
            month=4,
            year=2026,
            pto_days="[]",
            potentials='[{"issue_id": 114282, "name": "Suncoast", "total_hours": 12}]',
            output=str(output),
        )
        from unittest.mock import patch
        clients = [
            {"name": "IDERA", "issue_id": 98698, "issue_key": "DELIVERY-1223"},
            {"name": "Magic Memories", "issue_id": 95488, "issue_key": "DELIVERY-1310"},
        ]
        descriptions = {
            "potential": ["Pre-sales alignment"],
            "fixed": ["Delivery management"],
        }
        with patch("src.server._get_fixed_clients", return_value=clients), \
             patch("src.server.load_descriptions", return_value=descriptions):
            cmd_preview(args)

        assert output.exists()
        data = json.loads(output.read_text())
        assert "summary" in data
        assert "worklogs" in data

    def test_preview_summary_month(self, tmp_path):
        """summary.month matches year-month input."""
        from src.cli import cmd_preview
        import argparse

        output = tmp_path / "preview.json"
        args = argparse.Namespace(
            month=4, year=2026, pto_days="[]", potentials="[]", output=str(output),
        )
        from unittest.mock import patch
        clients = [{"name": "IDERA", "issue_id": 98698, "issue_key": "DELIVERY-1223"}]
        descriptions = {"potential": [], "fixed": ["Delivery management"]}
        with patch("src.server._get_fixed_clients", return_value=clients), \
             patch("src.server.load_descriptions", return_value=descriptions):
            cmd_preview(args)

        data = json.loads(output.read_text())
        assert data["summary"]["month"] == "2026-04"

    def test_preview_each_working_day_totals_8h(self, tmp_path):
        """Every working day in the worklogs sums to exactly 8h."""
        from src.cli import cmd_preview
        import argparse

        output = tmp_path / "preview.json"
        args = argparse.Namespace(
            month=4, year=2026, pto_days="[]",
            potentials='[{"issue_id": 114282, "name": "Suncoast", "total_hours": 12}]',
            output=str(output),
        )
        from unittest.mock import patch
        clients = [{"name": "IDERA", "issue_id": 98698, "issue_key": "DELIVERY-1223"}]
        descriptions = {"potential": ["Pre-sales"], "fixed": ["Delivery management"]}
        with patch("src.server._get_fixed_clients", return_value=clients), \
             patch("src.server.load_descriptions", return_value=descriptions):
            cmd_preview(args)

        data = json.loads(output.read_text())
        daily: dict[str, float] = {}
        for wl in data["worklogs"]:
            daily[wl["startDate"]] = daily.get(wl["startDate"], 0) + wl["timeSpentSeconds"] / 3600
        bad = {d: h for d, h in daily.items() if abs(h - 8.0) > 0.001}
        assert bad == {}, f"Days not totalling 8h: {bad}"

    def test_preview_creates_parent_dirs(self, tmp_path):
        """--output path with missing parent dirs is created automatically."""
        from src.cli import cmd_preview
        import argparse

        output = tmp_path / "nested" / "deep" / "preview.json"
        args = argparse.Namespace(
            month=4, year=2026, pto_days="[]", potentials="[]", output=str(output),
        )
        from unittest.mock import patch
        clients = [{"name": "IDERA", "issue_id": 98698, "issue_key": "DELIVERY-1223"}]
        descriptions = {"potential": [], "fixed": ["Delivery management"]}
        with patch("src.server._get_fixed_clients", return_value=clients), \
             patch("src.server.load_descriptions", return_value=descriptions):
            cmd_preview(args)

        assert output.exists()
