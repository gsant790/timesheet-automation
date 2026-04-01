# Timesheet Automation

Automated Tempo timesheet filling for AgileEngine delivery managers.

## What This Does

Fills monthly Jira/Tempo timesheets by:
1. Asking about PTO/vacation days and client changes
2. Auto-detecting "potential" clients (issues containing "potential" in name)
3. Distributing hours: potentials get tracked time, fixed clients fill remaining to 8h/day
4. Submitting worklogs via Tempo REST API v4

## Tech Stack

- Python 3.11+
- MCP server (FastMCP via mcp SDK) — exposes tools to Claude Code
- Tempo REST API v4 (`https://api.tempo.io/4/`)
- Jira Cloud REST API (for issue ID resolution)

## Project Structure

```
mcp-server/
  src/
    __init__.py
    server.py        — MCP server entry point, 4 tool definitions
    config.py        — Loads .env vars and YAML config files
    jira_client.py   — Jira Cloud API: issue search, key→ID resolution
    tempo_client.py  — Tempo API v4: worklog creation, batch submit with retry
    timesheet.py     — Hour distribution algorithm
  tests/
    __init__.py
    test_config.py
    test_jira_client.py
    test_tempo_client.py
    test_timesheet.py
    test_server.py
  pyproject.toml
  .venv/             — Virtual environment (gitignored)
data/
  clients.yaml       — Fixed client definitions (Jira issue keys)
  descriptions.yaml  — Worklog description pools (potential + fixed)
skills/
  timesheet.md       — /timesheet skill for conversational flow
.claude/
  settings.json      — MCP server registration
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `resolve_potential` | Search Jira for potential client issues by name |
| `get_fixed_clients` | Load fixed clients from YAML, resolve Jira issue IDs |
| `preview_timesheet` | Calculate hour distribution, return summary + worklogs |
| `submit_worklogs` | Submit worklog batch to Tempo API |

## Usage

Run `/timesheet` in Claude Code. It walks through: month selection, PTO, potentials, fixed client changes, preview, and submit.

## Running Tests

```bash
cd mcp-server
.venv/bin/python -m pytest tests/ -v
```

22 tests covering config, Jira client, Tempo client, distribution algorithm, and server integration.

## Key Rules

- Potentials are identified by "potential" in the Jira issue name
- Always fill 8h/day, Mon-Fri
- Potentials: max ~4h/week each, spread across 2-3 days/week
- Fixed clients: fill remaining hours, distributed evenly
- All hour values are in 0.25h (quarter-hour) increments
- Tempo API uses `issueId` (integer), not issue keys — resolved via Jira API

## Credentials

Never commit `.env`. Copy `.env.example` and fill in your tokens.
