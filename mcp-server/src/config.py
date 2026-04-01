"""Configuration loader for timesheet automation.

Loads environment variables from .env and YAML config files
from the data/ directory.
"""

import os
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).parent.parent.parent / "data"

REQUIRED_ENV_VARS = [
    "TEMPO_API_TOKEN",
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
]


def load_env() -> dict:
    """Load required environment variables.

    Returns dict with lowercase keys: tempo_api_token, jira_base_url, etc.
    Raises ValueError if any required var is missing.
    """
    env = {}
    for var in REQUIRED_ENV_VARS:
        value = os.environ.get(var)
        if not value:
            raise ValueError(
                f"Missing required environment variable: {var}. "
                f"Set it in .env or export it."
            )
        env[var.lower()] = value
    return env


def load_clients(path: Path | None = None) -> list[dict]:
    """Load fixed client definitions from clients.yaml.

    Each client has: name, issue_key.
    """
    path = path or (DATA_DIR / "clients.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("fixed_clients", [])


def load_descriptions(path: Path | None = None) -> dict[str, list[str]]:
    """Load worklog description pools from descriptions.yaml.

    Returns dict with 'potential' and 'fixed' keys, each a list of strings.
    """
    path = path or (DATA_DIR / "descriptions.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    return {
        "potential": data.get("potential", []),
        "fixed": data.get("fixed", []),
    }
