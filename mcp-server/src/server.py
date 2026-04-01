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
