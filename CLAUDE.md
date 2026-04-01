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
- MCP server (mcp SDK) — exposes tools to Claude Code
- Tempo REST API v4 (`https://api.tempo.io/4/`)
- Jira Cloud REST API (for issue ID resolution)

## Project Structure

```
mcp-server/          — MCP server exposing timesheet tools
  src/
    server.py        — MCP server entry point
    tempo_client.py  — Tempo API client
    jira_client.py   — Jira API client (issue resolution)
    timesheet.py     — Hour distribution logic
    config.py        — Configuration loading
data/
  clients.yaml       — Fixed client definitions (Jira project keys, default hours)
```

## Key Rules

- Potentials are identified by "potential" in the Jira issue name
- Always fill 8h/day, Mon-Fri
- Potentials: max ~4h/week each, spread across ~3 days
- Fixed clients: fill remaining hours, distributed evenly
- Tempo API uses `issueId` (integer), not issue keys — resolve via Jira API

## Credentials

Never commit `.env`. Copy `.env.example` and fill in your tokens.
