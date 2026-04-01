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
