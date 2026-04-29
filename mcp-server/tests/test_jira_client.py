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
            method="POST",
            url="https://test.atlassian.net/rest/api/3/search/jql",
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
