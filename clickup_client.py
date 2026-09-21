"""
Thin wrapper around the ClickUp API v2 - exposes only the operations this
automation needs: fetching filtered tasks, creating a task, updating a task status.
"""
import time
from typing import Any

import requests

BASE_URL = "https://api.clickup.com/api/v2"


class ClickUpClient:
    def __init__(self, api_token: str, max_retries: int = 3):
        # Note: the Authorization header uses the token directly, without "Bearer"
        self._headers = {"Authorization": api_token, "Content-Type": "application/json"}
        self._max_retries = max_retries

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{BASE_URL}{path}"
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            response = requests.request(method, url, headers=self._headers, timeout=30, **kwargs)

            if response.status_code == 429:
                # Rate limit exceeded (100/min) - wait until the counter resets
                wait_seconds = int(response.headers.get("X-RateLimit-Reset", 30))
                time.sleep(max(wait_seconds, 5))
                continue

            if response.ok:
                return response.json()

            error = requests.HTTPError(f"{response.status_code}: {response.text}")

            # Auth errors (invalid/expired token) won't recover on retry - fail fast
            if response.status_code in (401, 403):
                raise error

            last_error = error
            if attempt < self._max_retries:
                time.sleep(2 * attempt)

        raise RuntimeError(f"Request failed after {self._max_retries} attempts: {path}") from last_error

    def get_filtered_tasks(self, team_id: str, list_id: str, status: str) -> list[dict]:
        """Fetch only the tasks in a given status within a given list."""
        params = {
            "list_ids[]": list_id,
            "statuses[]": status,
            "include_closed": "true",
        }
        data = self._request("GET", f"/team/{team_id}/task", params=params)
        return data.get("tasks", [])

    def create_task(self, list_id: str, name: str, description: str, status: str) -> dict:
        payload = {"name": name, "description": description, "status": status}
        return self._request("POST", f"/list/{list_id}/task", json=payload)

    def update_task_status(self, task_id: str, status: str) -> dict:
        return self._request("PUT", f"/task/{task_id}", json={"status": status})

    @staticmethod
    def task_url(task_id: str) -> str:
        return f"https://app.clickup.com/t/{task_id}"
