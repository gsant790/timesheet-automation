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
