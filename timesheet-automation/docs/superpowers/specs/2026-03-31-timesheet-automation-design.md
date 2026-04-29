# Timesheet Automation — Design Spec

**Date:** 2026-03-31
**Status:** Approved
**Target:** End of April 2026

## Problem

Monthly Tempo timesheet filling is manual and tedious. Gonzalo needs to log 8h/day across fixed clients and rotating potentials, with accurate tracking of potential (pre-sales) hours since they're funded from a different revenue source.

## Solution

A Python MCP server exposing Tempo/Jira tools + a `/timesheet` Claude Code skill that orchestrates the conversational flow.

## Architecture

```
┌─────────────────────────────────────────────┐
│  /timesheet skill (Claude Code)             │
│  - Asks pre-fill questions                  │
│  - Calls MCP tools                          │
│  - Shows preview, gets approval             │
│  - Triggers submission                      │
└──────────────┬──────────────────────────────┘
               │ MCP tool calls
┌──────────────▼──────────────────────────────┐
│  MCP Server (Python)                        │
│                                             │
│  Tools:                                     │
│  - resolve_potential(client_name)           │
│  - get_fixed_clients()                      │
│  - preview_timesheet(...)                   │
│  - submit_worklogs(worklogs[])              │
│                                             │
│  Internal modules:                          │
│  - tempo_client.py  → Tempo REST API v4     │
│  - jira_client.py   → Jira Cloud REST API   │
│  - timesheet.py     → Distribution logic    │
│  - config.py        → Env + YAML loading    │
└──────────────┬──────────────────────────────┘
               │ HTTPS
       ┌───────┴───────┐
       ▼               ▼
  Tempo API v4    Jira Cloud API
```

## MCP Tools

### `resolve_potential(client_name: str) → {issue_key, issue_id, full_name}`

Searches Jira for issues in the "Engineering Support" project where summary contains both "Potential" and the given client name. Returns the matching issue's key, integer ID, and full summary.

**Jira API call:** `GET /rest/api/3/search?jql=project="Engineering Support" AND summary ~ "Potential" AND summary ~ "{client_name}"&fields=summary`

**Disambiguation:** If multiple issues match (e.g., two BiometryX potentials), return all matches and let the skill/user pick the correct one. In practice, most client names are unique enough for a single match.

### `get_fixed_clients() → [{name, issue_key, issue_id}]`

Reads `data/clients.yaml` and returns the fixed client list. Issue IDs are resolved via Jira API on first call and cached for the session.

**clients.yaml structure:**
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

### `preview_timesheet(month, year, pto_days, potentials, client_overrides?) → {summary, daily_breakdown, worklogs[]}`

**Inputs:**
- `month` (int): 1-12
- `year` (int): e.g. 2026
- `pto_days` (list[str]): Dates in YYYY-MM-DD format, e.g. ["2026-04-10", "2026-04-17"]
- `potentials` (list[dict]): Each has `{issue_id, client_name, hours_per_week}`
- `client_overrides` (dict, optional): Override fixed client list for this run (add/remove)

**Distribution algorithm:**
1. Calculate working days = weekdays in month − PTO days
2. Calculate weeks (working days / 5, rounded)
3. For each potential: monthly_hours = hours_per_week × weeks
4. Total potential hours = sum of all potential monthly hours
5. Remaining hours = (working_days × 8) − total potential hours
6. Fixed client hours each = remaining hours / number of fixed clients
7. Round all values to nearest 0.25h (15-minute increments)

**Daily distribution:**
- Each potential's weekly hours are spread across 2-3 days per week (not all 5)
- Rotation pattern varies week-to-week so the same potential isn't always on Monday
- Fixed clients fill the remaining hours each day, split evenly
- Every day totals exactly 8h

**Output:**
```json
{
  "summary": {
    "month": "April 2026",
    "working_days": 19,
    "pto_days": 2,
    "total_hours": 152,
    "clients": [
      {"name": "Suncoast", "type": "potential", "weekly_hours": 3.0, "monthly_hours": 12.0, "issue_key": "ES-2483799"},
      {"name": "IDERA", "type": "fixed", "monthly_hours": 32.0, "issue_key": "DELIVERY-1223"}
    ]
  },
  "worklogs": [
    {"issueId": 114282, "timeSpentSeconds": 5400, "startDate": "2026-04-01", "description": "..."},
    ...
  ]
}
```

### `submit_worklogs(worklogs: list[dict]) → {submitted, failed, errors[]}`

Takes the worklog list from `preview_timesheet` and POSTs each to Tempo API v4.

**Tempo API call per worklog:** `POST https://api.tempo.io/4/worklogs`
```json
{
  "issueId": 114282,
  "timeSpentSeconds": 5400,
  "startDate": "2026-04-15",
  "description": "Engagement discussions with POCs and stakeholders"
}
```

**Error handling:**
- Retries failed worklogs once (transient 5xx errors)
- Returns count of submitted vs failed, with error details
- Rate limited to 5 req/sec (Tempo API limit)

## Worklog Descriptions

Descriptions are randomly selected from pools per client type to avoid repetitive entries.

**Potential (pre-sales) descriptions:**
- "Pre-sales alignment and technical analysis"
- "Discovery meetings and proposal preparation"
- "Engagement discussions with POCs and stakeholders"
- "Technical research and solution scoping"
- "Starter lead coordination and team evaluation"

**Fixed client (account management) descriptions:**
- "Stakeholder alignment and account review"
- "Revenue and gross margin tracking"
- "Account health monitoring and escalation management"
- "Client engagement and delivery oversight"
- "Strategic planning and relationship management"

Selection rule: same client won't get the same description on consecutive days.

## `/timesheet` Skill Flow

The skill orchestrates this conversation:

1. **Month prompt:** "What month? (default: current month)"
2. **PTO prompt:** "Any PTO or vacation days this month?"
3. **Potentials prompt:** "Which potentials did you work on this month, and roughly how many hours per week each?"
4. **Client changes prompt:** "Any changes to your fixed clients? (new, removed)"
5. **Resolution:** Calls `resolve_potential` per potential, `get_fixed_clients` for fixed clients
6. **Preview:** Calls `preview_timesheet`, displays summary table and asks for approval
7. **Adjustment loop:** If user wants changes, recalculate and show again
8. **Submission:** On approval, calls `submit_worklogs`, reports result

## Project Structure

```
timesheet-automation/
  .env                          ← Tempo + Jira tokens (gitignored)
  .env.example                  ← Template
  CLAUDE.md                     ← Project context
  data/
    clients.yaml                ← Fixed client definitions
    descriptions.yaml           ← Description pools for worklogs
  mcp-server/
    pyproject.toml              ← Python deps
    src/
      __init__.py
      server.py                 ← MCP server entry, tool definitions
      tempo_client.py           ← Tempo API v4 client (httpx)
      jira_client.py            ← Jira Cloud API client (httpx)
      timesheet.py              ← Distribution algorithm
      config.py                 ← Loads .env + YAML config
    tests/
      test_timesheet.py         ← Distribution algorithm tests
      test_tempo_client.py      ← API client tests (mocked)
  skills/
    timesheet.md                ← /timesheet skill definition
```

## Configuration

**Environment variables (.env):**
- `TEMPO_API_TOKEN` — Tempo REST API bearer token
- `JIRA_BASE_URL` — `https://agileenginecloud.atlassian.net`
- `JIRA_EMAIL` — `gonzalo.santourian@agileengine.com`
- `JIRA_API_TOKEN` — Jira Cloud API token

**clients.yaml** — maintained manually, updated when fixed client roster changes.

**descriptions.yaml** — description pools, rarely changed.

## Constraints & Assumptions

- Gonzalo always fills the timesheet on the last day of the month, from scratch (no partial fills)
- Working days are Mon-Fri; Gonzalo works holidays unless explicit PTO
- Potentials are identified by "Potential" in the Jira issue summary within the "Engineering Support" project
- Fixed clients always log against their "Delivery Management" issue (one issue per client)
- All time values round to 0.25h (15-minute increments)
- Each day always totals exactly 8h
- Tempo API rate limit: 5 requests/second — a full month (~100 worklogs) takes ~20 seconds
