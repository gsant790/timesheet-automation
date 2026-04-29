import os
from pathlib import Path

import pytest
import yaml


def test_load_env_reads_required_vars(tmp_path, monkeypatch):
    """Config loads all required env vars."""
    from src.config import load_env

    monkeypatch.setenv("TEMPO_API_TOKEN", "test-tempo-token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-jira-token")

    env = load_env()
    assert env["tempo_api_token"] == "test-tempo-token"
    assert env["jira_base_url"] == "https://test.atlassian.net"
    assert env["jira_email"] == "test@test.com"
    assert env["jira_api_token"] == "test-jira-token"


def test_load_env_raises_on_missing_var(monkeypatch):
    """Config raises if a required env var is missing."""
    from src.config import load_env

    monkeypatch.delenv("TEMPO_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="TEMPO_API_TOKEN"):
        load_env()


def test_load_clients(tmp_path):
    """Config loads fixed clients from YAML."""
    from src.config import load_clients

    clients_file = tmp_path / "clients.yaml"
    clients_file.write_text(yaml.dump({
        "fixed_clients": [
            {"name": "IDERA", "issue_key": "DELIVERY-1223"},
            {"name": "Magic Memories", "issue_key": "DELIVERY-1310"},
        ]
    }))

    clients = load_clients(clients_file)
    assert len(clients) == 2
    assert clients[0]["name"] == "IDERA"
    assert clients[0]["issue_key"] == "DELIVERY-1223"


def test_load_descriptions(tmp_path):
    """Config loads description pools from YAML."""
    from src.config import load_descriptions

    desc_file = tmp_path / "descriptions.yaml"
    desc_file.write_text(yaml.dump({
        "potential": ["Pre-sales alignment", "Discovery meetings"],
        "fixed": ["Stakeholder alignment", "Revenue tracking"],
    }))

    descs = load_descriptions(desc_file)
    assert len(descs["potential"]) == 2
    assert len(descs["fixed"]) == 2
