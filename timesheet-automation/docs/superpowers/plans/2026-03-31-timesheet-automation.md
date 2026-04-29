# Timesheet Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server + `/timesheet` Claude Code skill that automates monthly Tempo timesheet filling.

**Architecture:** MCP server exposes 4 tools (resolve_potential, get_fixed_clients, preview_timesheet, submit_worklogs) backed by Tempo REST API v4 and Jira Cloud API. A `/timesheet` skill orchestrates the conversational flow — asks pre-fill questions, previews the distribution, and submits on approval.

**Tech Stack:** Python 3.11+, FastMCP (mcp SDK), httpx, PyYAML, pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `mcp-server/src/config.py` | Loads .env and YAML config files |
| `mcp-server/src/jira_client.py` | Jira Cloud REST API — issue search and key→ID resolution |
| `mcp-server/src/tempo_client.py` | Tempo REST API v4 — create worklogs |
| `mcp-server/src/timesheet.py` | Distribution algorithm — turns inputs into worklog list |
| `mcp-server/src/server.py` | MCP server entry point, tool definitions |
| `mcp-server/tests/test_timesheet.py` | Unit tests for distribution algorithm |
| `mcp-server/tests/test_jira_client.py` | Tests for Jira client (mocked HTTP) |
| `mcp-server/tests/test_tempo_client.py` | Tests for Tempo client (mocked HTTP) |
| `mcp-server/tests/test_server.py` | Integration tests for MCP tools |
| `data/clients.yaml` | Fixed client definitions |
| `data/descriptions.yaml` | Worklog description pools |
| `.claude/settings.json` | MCP server registration |
| `skills/timesheet.md` | `/timesheet` skill definition |

---

### Task 1: Configuration Module

**Files:**
- Create: `mcp-server/src/config.py`
- Create: `data/descriptions.yaml`
- Modify: `data/clients.yaml`
- Create: `mcp-server/tests/test_config.py`

- [ ] **Step 1: Write test for config loading**

Create `mcp-server/tests/__init__.py` (empty) and `mcp-server/tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Write data files**

Update `data/clients.yaml`:

```yaml
fixed_clients:
  - name: "IDERA"
    issue_key: "DELIVERY-1223"
  - name: "Magic Memories"
    issue_key: "DELIVERY-1310"
  - name: "Madison Reed"
    issue_key: "DELIVERY-680"
  - name: "iRhythm"
    issue_key: "DELIVERY-1025"
```

Create `data/descriptions.yaml`:

```yaml
potential:
  - "Pre-sales alignment and technical analysis"
  - "Discovery meetings and proposal preparation"
  - "Engagement discussions with POCs and stakeholders"
  - "Technical research and solution scoping"
  - "Starter lead coordination and team evaluation"

fixed:
  - "Stakeholder alignment and account review"
  - "Revenue and gross margin tracking"
  - "Account health monitoring and escalation management"
  - "Client engagement and delivery oversight"
  - "Strategic planning and relationship management"
```

- [ ] **Step 4: Implement config module**

Create `mcp-server/src/config.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_config.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add mcp-server/src/config.py mcp-server/tests/__init__.py mcp-server/tests/test_config.py data/clients.yaml data/descriptions.yaml
git commit -m "feat: add configuration module with env, clients, and descriptions loading"
```

---

### Task 2: Jira Client

**Files:**
- Create: `mcp-server/src/jira_client.py`
- Create: `mcp-server/tests/test_jira_client.py`

- [ ] **Step 1: Write tests for Jira client**

Create `mcp-server/tests/test_jira_client.py`:

```python
import httpx
import pytest


def _mock_search_response(issues):
    """Build a mock Jira search response."""
    return {
        "issues": [
            {
                "id": str(issue["id"]),
                "key": issue["key"],
                "fields": {"summary": issue["summary"]},
            }
            for issue in issues
        ]
    }


def _mock_issue_response(issue_id, key):
    """Build a mock Jira issue response."""
    return {"id": str(issue_id), "key": key}


class TestResolvePotential:
    def test_single_match(self, httpx_mock):
        from src.jira_client import JiraClient

        httpx_mock.add_response(
            url=httpx.URL(
                "https://test.atlassian.net/rest/api/3/search",
                params={
                    "jql": 'project="Engineering Support" AND summary ~ "Potential" AND summary ~ "Suncoast"',
                    "fields": "summary",
                    "maxResults": "10",
                },
            ),
            json=_mock_search_response([
                {"id": 114282, "key": "ES-2483799", "summary": "Texas - Potential[L] - Suncoast Post-Tension"},
            ]),
        )

        client = JiraClient("https://test.atlassian.net", "test@test.com", "token")
        results = client.resolve_potential("Suncoast")

        assert len(results) == 1
        assert results[0]["issue_key"] == "ES-2483799"
        assert results[0]["issue_id"] == 114282
        assert "Suncoast" in results[0]["full_name"]

    def test_multiple_matches(self, httpx_mock):
        from src.jira_client import JiraClient

        httpx_mock.add_response(
            json=_mock_search_response([
                {"id": 111, "key": "ES-111", "summary": "Texas - Potential[XS] - BiometryX"},
                {"id": 222, "key": "ES-222", "summary": "Austin - Potential[XS] - BiometryX"},
            ]),
        )

        client = JiraClient("https://test.atlassian.net", "test@test.com", "token")
        results = client.resolve_potential("BiometryX")

        assert len(results) == 2

    def test_no_match(self, httpx_mock):
        from src.jira_client import JiraClient

        httpx_mock.add_response(json=_mock_search_response([]))

        client = JiraClient("https://test.atlassian.net", "test@test.com", "token")
        results = client.resolve_potential("NonExistent")

        assert len(results) == 0


class TestResolveIssueId:
    def test_resolves_key_to_id(self, httpx_mock):
        from src.jira_client import JiraClient

        httpx_mock.add_response(
            url=httpx.URL("https://test.atlassian.net/rest/api/3/issue/DELIVERY-1223"),
            json=_mock_issue_response(98698, "DELIVERY-1223"),
        )

        client = JiraClient("https://test.atlassian.net", "test@test.com", "token")
        issue_id = client.resolve_issue_id("DELIVERY-1223")

        assert issue_id == 98698
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
pip install pytest-httpx
python3 -m pytest tests/test_jira_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.jira_client'`

- [ ] **Step 3: Implement Jira client**

Create `mcp-server/src/jira_client.py`:

```python
"""Jira Cloud REST API client.

Handles issue search (for potential resolution) and issue key → ID resolution.
Uses httpx for HTTP requests with Basic auth.
"""

import httpx


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    def resolve_potential(self, client_name: str) -> list[dict]:
        """Search for potential issues matching a client name.

        Searches Engineering Support project for issues with 'Potential'
        and the client name in the summary.

        Returns list of {issue_key, issue_id, full_name}.
        """
        jql = (
            f'project="Engineering Support" '
            f'AND summary ~ "Potential" '
            f'AND summary ~ "{client_name}"'
        )
        resp = self._client.get(
            "/rest/api/3/search",
            params={"jql": jql, "fields": "summary", "maxResults": "10"},
        )
        resp.raise_for_status()
        data = resp.json()

        return [
            {
                "issue_key": issue["key"],
                "issue_id": int(issue["id"]),
                "full_name": issue["fields"]["summary"],
            }
            for issue in data.get("issues", [])
        ]

    def resolve_issue_id(self, issue_key: str) -> int:
        """Resolve a Jira issue key (e.g. DELIVERY-1223) to its integer ID."""
        resp = self._client.get(f"/rest/api/3/issue/{issue_key}")
        resp.raise_for_status()
        return int(resp.json()["id"])

    def close(self):
        self._client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_jira_client.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/jira_client.py mcp-server/tests/test_jira_client.py
git commit -m "feat: add Jira client for potential resolution and issue ID lookup"
```

---

### Task 3: Tempo Client

**Files:**
- Create: `mcp-server/src/tempo_client.py`
- Create: `mcp-server/tests/test_tempo_client.py`

- [ ] **Step 1: Write tests for Tempo client**

Create `mcp-server/tests/test_tempo_client.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_tempo_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.tempo_client'`

- [ ] **Step 3: Implement Tempo client**

Create `mcp-server/src/tempo_client.py`:

```python
"""Tempo REST API v4 client.

Handles worklog creation with rate limiting and batch submission.
"""

import time

import httpx

TEMPO_API_BASE = "https://api.tempo.io/4"
RATE_LIMIT_DELAY = 0.2  # 5 req/sec = 200ms between requests


class TempoClient:
    def __init__(self, api_token: str):
        self._client = httpx.Client(
            base_url=TEMPO_API_BASE,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    def create_worklog(
        self, issue_id: int, date: str, seconds: int, description: str
    ) -> dict:
        """Create a single Tempo worklog.

        Args:
            issue_id: Jira issue integer ID.
            date: Date string YYYY-MM-DD.
            seconds: Time spent in seconds.
            description: Worklog description.

        Returns:
            Tempo API response dict.
        """
        payload = {
            "issueId": issue_id,
            "timeSpentSeconds": seconds,
            "startDate": date,
            "description": description,
        }
        resp = self._client.post("/worklogs", json=payload)
        resp.raise_for_status()
        return resp.json()

    def submit_batch(self, worklogs: list[dict]) -> dict:
        """Submit a batch of worklogs with rate limiting and retry.

        Each worklog dict must have: issueId, timeSpentSeconds, startDate, description.

        Returns: {submitted: int, failed: int, errors: list[str]}
        """
        submitted = 0
        failed = 0
        errors = []

        for i, wl in enumerate(worklogs):
            if i > 0:
                time.sleep(RATE_LIMIT_DELAY)

            try:
                self.create_worklog(
                    issue_id=wl["issueId"],
                    date=wl["startDate"],
                    seconds=wl["timeSpentSeconds"],
                    description=wl["description"],
                )
                submitted += 1
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    # Retry once for server errors
                    time.sleep(RATE_LIMIT_DELAY)
                    try:
                        self.create_worklog(
                            issue_id=wl["issueId"],
                            date=wl["startDate"],
                            seconds=wl["timeSpentSeconds"],
                            description=wl["description"],
                        )
                        submitted += 1
                        continue
                    except Exception:
                        pass
                failed += 1
                errors.append(
                    f"Failed worklog for issue {wl['issueId']} on {wl['startDate']}: "
                    f"{e.response.status_code}"
                )

        return {"submitted": submitted, "failed": failed, "errors": errors}

    def close(self):
        self._client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_tempo_client.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/tempo_client.py mcp-server/tests/test_tempo_client.py
git commit -m "feat: add Tempo client with batch submission and retry logic"
```

---

### Task 4: Distribution Algorithm

This is the core logic. Most complex task — lots of tests.

**Files:**
- Create: `mcp-server/src/timesheet.py`
- Create: `mcp-server/tests/test_timesheet.py`

- [ ] **Step 1: Write tests for distribution algorithm**

Create `mcp-server/tests/test_timesheet.py`:

```python
import pytest
from datetime import date


class TestGetWorkingDays:
    def test_april_2026_no_pto(self):
        from src.timesheet import get_working_days

        days = get_working_days(4, 2026, [])
        # April 2026: 22 weekdays (Wed Apr 1 to Thu Apr 30)
        assert len(days) == 22
        # All should be weekdays
        for d in days:
            assert d.weekday() < 5

    def test_with_pto_days(self):
        from src.timesheet import get_working_days

        pto = ["2026-04-10", "2026-04-17"]
        days = get_working_days(4, 2026, pto)
        assert len(days) == 20
        assert date(2026, 4, 10) not in days
        assert date(2026, 4, 17) not in days

    def test_pto_on_weekend_ignored(self):
        from src.timesheet import get_working_days

        # April 4, 2026 is a Saturday
        pto = ["2026-04-04"]
        days = get_working_days(4, 2026, pto)
        assert len(days) == 22  # no change


class TestDistributeHours:
    def test_no_potentials(self):
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        fixed = [
            {"name": "IDERA", "issue_id": 1},
            {"name": "Magic Memories", "issue_id": 2},
        ]
        result = distribute_hours(days, [], fixed)

        # Every day should total 8h
        for day_entry in result:
            total = sum(e["hours"] for e in day_entry["entries"])
            assert total == 8.0

        # Each fixed client should get 4h/day (8 / 2 clients)
        first_day = result[0]
        for entry in first_day["entries"]:
            assert entry["hours"] == 4.0

    def test_with_potentials(self):
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        potentials = [
            {"name": "Suncoast", "issue_id": 100, "hours_per_week": 3.0},
        ]
        fixed = [
            {"name": "IDERA", "issue_id": 1},
            {"name": "Magic Memories", "issue_id": 2},
        ]
        result = distribute_hours(days, potentials, fixed)

        # Every day totals 8h
        for day_entry in result:
            total = sum(e["hours"] for e in day_entry["entries"])
            assert abs(total - 8.0) < 0.01

        # Suncoast should appear on some days but not all
        suncoast_days = [
            d for d in result
            if any(e["name"] == "Suncoast" for e in d["entries"])
        ]
        assert 0 < len(suncoast_days) < len(result)

    def test_all_values_quarter_hour(self):
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        potentials = [
            {"name": "A", "issue_id": 10, "hours_per_week": 3.0},
            {"name": "B", "issue_id": 20, "hours_per_week": 2.0},
        ]
        fixed = [
            {"name": "C", "issue_id": 1},
            {"name": "D", "issue_id": 2},
            {"name": "E", "issue_id": 3},
        ]
        result = distribute_hours(days, potentials, fixed)

        for day_entry in result:
            for entry in day_entry["entries"]:
                # hours should be a multiple of 0.25
                assert entry["hours"] % 0.25 == 0, (
                    f"Non-quarter-hour value: {entry['hours']} for {entry['name']} on {day_entry['date']}"
                )

    def test_potential_max_days_per_week(self):
        """Each potential should appear on 2-3 days per week, not all 5."""
        from src.timesheet import distribute_hours, get_working_days

        days = get_working_days(4, 2026, [])
        potentials = [
            {"name": "Suncoast", "issue_id": 100, "hours_per_week": 4.0},
        ]
        fixed = [{"name": "IDERA", "issue_id": 1}]
        result = distribute_hours(days, potentials, fixed)

        # Group by week (ISO week number)
        from collections import defaultdict
        weeks = defaultdict(int)
        for d in result:
            if any(e["name"] == "Suncoast" for e in d["entries"]):
                week_num = d["date"].isocalendar()[1]
                weeks[week_num] += 1

        for week_num, count in weeks.items():
            assert count <= 3, f"Suncoast appeared {count} days in week {week_num}"


class TestBuildWorklogs:
    def test_worklogs_have_required_fields(self):
        from src.timesheet import distribute_hours, get_working_days, build_worklogs

        days = get_working_days(4, 2026, [])
        fixed = [{"name": "IDERA", "issue_id": 98698}]
        distribution = distribute_hours(days, [], fixed)
        descriptions = {
            "potential": ["Pre-sales work"],
            "fixed": ["Delivery management"],
        }

        worklogs = build_worklogs(distribution, descriptions)

        assert len(worklogs) > 0
        for wl in worklogs:
            assert "issueId" in wl
            assert "timeSpentSeconds" in wl
            assert "startDate" in wl
            assert "description" in wl
            assert wl["timeSpentSeconds"] > 0
            assert isinstance(wl["issueId"], int)

    def test_descriptions_vary(self):
        """Same client should not get same description every day."""
        from src.timesheet import distribute_hours, get_working_days, build_worklogs

        days = get_working_days(4, 2026, [])
        fixed = [{"name": "IDERA", "issue_id": 98698}]
        distribution = distribute_hours(days, [], fixed)
        descriptions = {
            "potential": ["Pre-sales work"],
            "fixed": [
                "Stakeholder alignment and account review",
                "Revenue and gross margin tracking",
                "Account health monitoring",
            ],
        }

        worklogs = build_worklogs(distribution, descriptions)
        idera_descriptions = [wl["description"] for wl in worklogs if wl["issueId"] == 98698]

        # With 22 work days and 3 descriptions, we should see variety
        unique = set(idera_descriptions)
        assert len(unique) > 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_timesheet.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.timesheet'`

- [ ] **Step 3: Implement distribution algorithm**

Create `mcp-server/src/timesheet.py`:

```python
"""Timesheet distribution algorithm.

Takes month parameters, potentials, and fixed clients, then generates
a day-by-day distribution of hours that always totals 8h/day.
"""

import calendar
import random
from datetime import date, timedelta


def get_working_days(month: int, year: int, pto_days: list[str]) -> list[date]:
    """Get all working days (Mon-Fri) in a month, excluding PTO.

    Args:
        month: 1-12
        year: e.g. 2026
        pto_days: List of date strings "YYYY-MM-DD" to exclude.

    Returns:
        Sorted list of date objects for working days.
    """
    pto_set = {date.fromisoformat(d) for d in pto_days}
    num_days = calendar.monthrange(year, month)[1]
    working = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5 and d not in pto_set:
            working.append(d)
    return working


def _round_quarter(hours: float) -> float:
    """Round to nearest 0.25h."""
    return round(hours * 4) / 4


def distribute_hours(
    working_days: list[date],
    potentials: list[dict],
    fixed_clients: list[dict],
) -> list[dict]:
    """Distribute 8h/day across potentials and fixed clients.

    Args:
        working_days: List of working day dates.
        potentials: Each has {name, issue_id, hours_per_week}.
        fixed_clients: Each has {name, issue_id}.

    Returns:
        List of {date, entries: [{name, issue_id, hours, type}]} per day.
        Every day's entries sum to exactly 8.0h.
    """
    daily_target = 8.0
    result = []

    # Group working days into weeks (Mon=0 based, group by ISO week)
    weeks: dict[int, list[date]] = {}
    for d in working_days:
        week_num = d.isocalendar()[1]
        weeks.setdefault(week_num, []).append(d)

    # For each potential, pre-assign which days of each week they appear on.
    # Spread across 2-3 days per week, rotating the pattern.
    potential_schedule: dict[str, set[date]] = {p["name"]: set() for p in potentials}

    for pot in potentials:
        days_per_week = min(3, max(2, round(pot["hours_per_week"] / 1.5)))
        offset = hash(pot["name"]) % 5  # deterministic but varied per potential

        for week_num, week_days in weeks.items():
            # Pick days_per_week days from this week, rotating start
            available = len(week_days)
            indices = []
            for i in range(days_per_week):
                idx = (offset + i * 2) % available  # spread out
                if idx not in indices:
                    indices.append(idx)
            # If we got duplicates, just pick first N unique
            indices = list(dict.fromkeys(indices))[:days_per_week]
            # Ensure we don't exceed available days
            indices = indices[:available]

            for idx in indices:
                potential_schedule[pot["name"]].add(week_days[idx])

            offset = (offset + 1) % 5  # rotate for next week

    # Build daily distribution
    for d in working_days:
        entries = []

        # Add potentials scheduled for today
        potential_hours_today = 0.0
        for pot in potentials:
            if d in potential_schedule[pot["name"]]:
                # Calculate hours for this day
                # Weekly hours spread across the days this potential appears this week
                week_num = d.isocalendar()[1]
                week_days_for_pot = [
                    wd for wd in weeks[week_num]
                    if wd in potential_schedule[pot["name"]]
                ]
                hours = _round_quarter(pot["hours_per_week"] / len(week_days_for_pot))
                entries.append({
                    "name": pot["name"],
                    "issue_id": pot["issue_id"],
                    "hours": hours,
                    "type": "potential",
                })
                potential_hours_today += hours

        # Distribute remaining hours to fixed clients
        remaining = daily_target - potential_hours_today
        if fixed_clients and remaining > 0:
            per_client = _round_quarter(remaining / len(fixed_clients))

            # Adjust for rounding: ensure total hits exactly 8h
            fixed_entries = []
            allocated = 0.0
            for i, client in enumerate(fixed_clients):
                if i == len(fixed_clients) - 1:
                    # Last client gets whatever is left to hit 8h exactly
                    hours = _round_quarter(remaining - allocated)
                else:
                    hours = per_client
                    allocated += hours
                fixed_entries.append({
                    "name": client["name"],
                    "issue_id": client["issue_id"],
                    "hours": hours,
                    "type": "fixed",
                })
            entries.extend(fixed_entries)

        result.append({"date": d, "entries": entries})

    return result


def build_worklogs(
    distribution: list[dict],
    descriptions: dict[str, list[str]],
) -> list[dict]:
    """Convert distribution into Tempo worklog payloads.

    Args:
        distribution: Output from distribute_hours.
        descriptions: {"potential": [...], "fixed": [...]}.

    Returns:
        List of {issueId, timeSpentSeconds, startDate, description}.
    """
    worklogs = []
    # Track last description per client to avoid consecutive repeats
    last_desc: dict[int, str] = {}

    for day in distribution:
        for entry in day["entries"]:
            pool = descriptions.get(entry["type"], ["Work"])
            # Pick a description that differs from last time
            available = [d for d in pool if d != last_desc.get(entry["issue_id"])]
            if not available:
                available = pool
            desc = random.choice(available)
            last_desc[entry["issue_id"]] = desc

            worklogs.append({
                "issueId": entry["issue_id"],
                "timeSpentSeconds": int(entry["hours"] * 3600),
                "startDate": day["date"].isoformat(),
                "description": desc,
            })

    return worklogs
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_timesheet.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/timesheet.py mcp-server/tests/test_timesheet.py
git commit -m "feat: add distribution algorithm for timesheet hour allocation"
```

---

### Task 5: MCP Server with Tool Definitions

**Files:**
- Create: `mcp-server/src/server.py`
- Create: `mcp-server/tests/test_server.py`

- [ ] **Step 1: Write integration test for MCP tools**

Create `mcp-server/tests/test_server.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_server.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.server'`

- [ ] **Step 3: Implement MCP server**

Create `mcp-server/src/server.py`:

```python
"""Timesheet Automation MCP Server.

Exposes tools for Tempo timesheet filling: resolve potentials,
get fixed clients, preview distribution, and submit worklogs.
Runs locally via stdio transport.
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .config import load_env, load_clients, load_descriptions
from .jira_client import JiraClient
from .tempo_client import TempoClient
from .timesheet import get_working_days, distribute_hours, build_worklogs

DATA_DIR = Path(__file__).parent.parent.parent / "data"

mcp = FastMCP("Timesheet Automation")


def _get_jira_client() -> JiraClient:
    env = load_env()
    return JiraClient(env["jira_base_url"], env["jira_email"], env["jira_api_token"])


def _get_tempo_client() -> TempoClient:
    env = load_env()
    return TempoClient(env["tempo_api_token"])


def _get_fixed_clients(clients_path: Path | None = None) -> list[dict]:
    """Load fixed clients and resolve their issue IDs via Jira API."""
    clients = load_clients(clients_path)
    jira = _get_jira_client()
    try:
        for client in clients:
            client["issue_id"] = jira.resolve_issue_id(client["issue_key"])
    finally:
        jira.close()
    return clients


def _preview_timesheet(
    month: int,
    year: int,
    pto_days: list[str],
    potentials: list[dict],
    clients_path: Path | None = None,
    descriptions_path: Path | None = None,
) -> str:
    """Internal preview logic, testable with custom paths."""
    fixed = _get_fixed_clients(clients_path)
    descriptions = load_descriptions(descriptions_path)
    working_days = get_working_days(month, year, pto_days)
    distribution = distribute_hours(working_days, potentials, fixed)
    worklogs = build_worklogs(distribution, descriptions)

    # Build summary
    total_hours = len(working_days) * 8.0
    client_summaries = []
    for pot in potentials:
        pot_hours = sum(
            e["hours"]
            for d in distribution
            for e in d["entries"]
            if e["issue_id"] == pot["issue_id"]
        )
        client_summaries.append({
            "name": pot["name"],
            "type": "potential",
            "weekly_hours": pot["hours_per_week"],
            "monthly_hours": pot_hours,
            "issue_id": pot["issue_id"],
        })
    for fc in fixed:
        fc_hours = sum(
            e["hours"]
            for d in distribution
            for e in d["entries"]
            if e["issue_id"] == fc["issue_id"]
        )
        client_summaries.append({
            "name": fc["name"],
            "type": "fixed",
            "monthly_hours": fc_hours,
            "issue_key": fc["issue_key"],
        })

    return json.dumps({
        "summary": {
            "month": f"{year}-{month:02d}",
            "working_days": len(working_days),
            "pto_days": len(pto_days),
            "total_hours": total_hours,
            "clients": client_summaries,
        },
        "worklogs": worklogs,
    }, indent=2)


@mcp.tool()
def resolve_potential(client_name: str) -> str:
    """Search for a potential client's Jira issue.

    Searches the Engineering Support project for issues with 'Potential'
    and the client name in the summary. Returns matching issues.

    Args:
        client_name: The client name to search for (e.g. "Suncoast", "BiometryX").

    Returns:
        JSON array of {issue_key, issue_id, full_name} matches.
    """
    jira = _get_jira_client()
    try:
        results = jira.resolve_potential(client_name)
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        jira.close()


@mcp.tool()
def get_fixed_clients() -> str:
    """Get the list of fixed clients from configuration.

    Reads clients.yaml and resolves each client's Jira issue key
    to its integer ID.

    Returns:
        JSON array of {name, issue_key, issue_id}.
    """
    try:
        clients = _get_fixed_clients()
        return json.dumps(clients, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def preview_timesheet(
    month: int,
    year: int,
    pto_days: str = "[]",
    potentials: str = "[]",
) -> str:
    """Preview the timesheet distribution without submitting.

    Calculates how hours will be distributed across the month
    for all potentials and fixed clients.

    Args:
        month: Month number (1-12).
        year: Year (e.g. 2026).
        pto_days: JSON array of PTO dates ["YYYY-MM-DD", ...].
        potentials: JSON array of potential clients, each with
            {issue_id: int, name: str, hours_per_week: float}.

    Returns:
        JSON with summary table and full worklog list for review.
    """
    try:
        pto_list = json.loads(pto_days)
        pot_list = json.loads(potentials)
        return _preview_timesheet(month, year, pto_list, pot_list)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def submit_worklogs(worklogs: str) -> str:
    """Submit worklogs to Tempo.

    Takes the worklog list from preview_timesheet and submits
    each one to the Tempo API.

    Args:
        worklogs: JSON array of worklog objects, each with
            {issueId, timeSpentSeconds, startDate, description}.

    Returns:
        JSON with {submitted, failed, errors} counts.
    """
    try:
        wl_list = json.loads(worklogs)
        tempo = _get_tempo_client()
        try:
            result = tempo.submit_batch(wl_list)
            return json.dumps(result, indent=2)
        finally:
            tempo.close()
    except Exception as e:
        return json.dumps({"error": str(e)})


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/test_server.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m pytest tests/ -v
```

Expected: All tests PASS (config: 4, jira: 4, tempo: 3, timesheet: 7, server: 2 = 20 total)

- [ ] **Step 6: Commit**

```bash
git add mcp-server/src/server.py mcp-server/tests/test_server.py
git commit -m "feat: add MCP server with all four timesheet tools"
```

---

### Task 6: MCP Server Registration & Virtual Environment

**Files:**
- Create: `.claude/settings.json`
- Modify: `mcp-server/pyproject.toml` (add pytest-httpx dependency)

- [ ] **Step 1: Add pytest-httpx to dev dependencies**

In `mcp-server/pyproject.toml`, update the dev dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "pytest-httpx>=0.30.0",
]
```

- [ ] **Step 2: Create virtual environment and install dependencies**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 3: Verify tests pass in the venv**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
.venv/bin/python -m pytest tests/ -v
```

Expected: All 20 tests PASS

- [ ] **Step 4: Register MCP server in Claude Code settings**

Create `.claude/settings.json`:

```json
{
  "mcpServers": {
    "timesheet": {
      "command": "mcp-server/.venv/bin/python3",
      "args": ["-m", "src.server"],
      "cwd": "mcp-server",
      "env": {}
    }
  }
}
```

- [ ] **Step 5: Add .venv to gitignore and commit**

Verify `.venv/` is already in `.gitignore` (it is, under `venv/` pattern — add explicit `.venv/` if needed).

```bash
git add .claude/settings.json mcp-server/pyproject.toml
git commit -m "feat: register MCP server and add dev dependencies"
```

---

### Task 7: `/timesheet` Skill

**Files:**
- Create: `skills/timesheet.md`

- [ ] **Step 1: Create the skill file**

Create `skills/timesheet.md`:

```markdown
---
name: timesheet
description: Fill monthly Tempo timesheet — asks about PTO, potentials, and fixed client changes, previews distribution, and submits worklogs
user_invocable: true
---

You are filling a monthly Tempo timesheet. Follow these steps exactly.

## Step 1: Month

Ask the user: "What month should I fill? (default: current month)"

If they don't specify, use the current month and year.

## Step 2: PTO / Vacation

Ask: "Any PTO or vacation days in [Month Year]? List specific dates, or say 'none'."

## Step 3: Potentials

Ask: "Which potentials did you work on this month, and roughly how many hours per week each?"

Example answer: "Suncoast ~3h, BiometryX ~2h, GeoTap ~1h"

For each potential named, call the `resolve_potential` tool with the client name. If multiple matches come back, ask the user to pick the right one.

## Step 4: Fixed Client Changes

Ask: "Any changes to your fixed clients this month? (new additions, removals, or 'no changes')"

If changes: update the `data/clients.yaml` file accordingly before proceeding.

## Step 5: Preview

Call `get_fixed_clients` to load the current fixed client list.

Then call `preview_timesheet` with:
- `month` and `year` from Step 1
- `pto_days` as JSON array of "YYYY-MM-DD" strings from Step 2
- `potentials` as JSON array: each entry is `{"issue_id": <id>, "name": "<name>", "hours_per_week": <hours>}` from Step 3

Display the summary to the user as a table:

| Client | Type | Weekly hrs | Monthly hrs | Issue |
|--------|------|-----------|-------------|-------|
| ... | potential | 3.0h | 12.0h | ES-... |
| ... | fixed | — | 32.0h | DELIVERY-... |

Then ask: "Does this look right, or do you want to adjust anything?"

If adjustments requested, recalculate with updated parameters and show again.

## Step 6: Submit

When the user approves (says "yes", "good", "ship it", "submit", etc.):

Extract the `worklogs` array from the preview response and pass it to `submit_worklogs` as a JSON string.

Report the result: "Done! Submitted X worklogs for [Month Year]. (Y failed, if any)"

## Important Notes

- Every day must total exactly 8 hours
- All values are in 0.25h (15-minute) increments
- Potentials appear on 2-3 days per week, not every day
- Fixed clients fill the remaining hours, split evenly
- Descriptions are auto-generated — no need to ask the user
```

- [ ] **Step 2: Register the skill in Claude Code settings**

Update `.claude/settings.json` to include the skill path. Actually, Claude Code auto-discovers skills from the `skills/` directory in the project root — no settings change needed. Verify by checking that the file exists at `skills/timesheet.md`.

- [ ] **Step 3: Commit**

```bash
git add skills/timesheet.md
git commit -m "feat: add /timesheet skill for conversational timesheet filling"
```

---

### Task 8: End-to-End Smoke Test

**Files:** No new files — manual verification.

- [ ] **Step 1: Verify MCP server starts**

```bash
cd /Users/gonzalosantourian/Projects/timesheet-automation/mcp-server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | .venv/bin/python3 -m src.server
```

Expected: JSON response with server capabilities (tools listed).

- [ ] **Step 2: Test resolve_potential against live Jira API**

Open Claude Code in the `timesheet-automation` project directory and run:

```
Call the resolve_potential tool with client_name "Suncoast"
```

Expected: Returns issue ES-2483799 with the Suncoast Post-Tension potential.

- [ ] **Step 3: Test get_fixed_clients against live Jira API**

```
Call the get_fixed_clients tool
```

Expected: Returns the 4 fixed clients from clients.yaml with resolved issue IDs.

- [ ] **Step 4: Test preview_timesheet**

```
Call preview_timesheet with month=4, year=2026, pto_days="[]", potentials='[{"issue_id": 114282, "name": "Suncoast", "hours_per_week": 3.0}]'
```

Expected: Summary showing 22 working days, Suncoast with ~12-13h monthly, fixed clients filling the rest. Total 176h.

- [ ] **Step 5: Test the /timesheet skill flow**

Run `/timesheet` in Claude Code and walk through the full flow (but do NOT submit — cancel before Step 6 since this is a test).

- [ ] **Step 6: Commit any fixes from smoke testing**

```bash
git add -A
git commit -m "fix: adjustments from end-to-end smoke testing"
```

Only if fixes were needed. Skip if everything passed clean.

---

### Task 9: Update CLAUDE.md and Clean Up

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with final project state**

Update `CLAUDE.md` to reflect the completed implementation — accurate project structure, instructions for running tests, and skill usage.

- [ ] **Step 2: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with final project structure and usage"
```
