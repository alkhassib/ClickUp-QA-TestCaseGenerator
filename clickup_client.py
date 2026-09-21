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

    def _request(self, method: str, path: str, retryable: bool = True, **kwargs: Any) -> dict:
        """Send a request, optionally retrying transient failures.

        `retryable` MUST be False for non-idempotent writes (e.g. creating a
        task): retrying a POST that ClickUp already applied would create a
        duplicate. See create_task.
        """
        url = f"{BASE_URL}{path}"
        max_attempts = self._max_retries if retryable else 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            response = requests.request(method, url, headers=self._headers, timeout=30, **kwargs)

            if response.status_code == 429:
                # Rate limit exceeded (100/min) - wait until the counter resets.
                # For non-retryable calls we surface it instead of blindly resending.
                if not retryable:
                    raise requests.HTTPError(f"429: {response.text}")
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
            if attempt < max_attempts:
                time.sleep(2 * attempt)

        if last_error is None:
            # Non-retryable call that failed on its single attempt.
            raise RuntimeError(f"Request failed: {path}")
        raise RuntimeError(f"Request failed after {max_attempts} attempts: {path}") from last_error

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
        # Not retryable: a POST that ClickUp already applied but answered with a
        # transient error would be duplicated on retry (one extra task).
        payload = {"name": name, "description": description, "status": status}
        return self._request("POST", f"/list/{list_id}/task", retryable=False, json=payload)

    def update_task_status(self, task_id: str, status: str) -> dict:
        return self._request("PUT", f"/task/{task_id}", json={"status": status})

    @staticmethod
    def task_url(task_id: str) -> str:
        return f"https://app.clickup.com/t/{task_id}"
