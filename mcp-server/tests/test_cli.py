"""Tests for the CLI (preview and submit subcommands)."""

import json
import sys

import pytest
import yaml


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")


def test_cli_module_imports():
    from src.cli import cmd_preview, cmd_submit, main  # noqa: F401
