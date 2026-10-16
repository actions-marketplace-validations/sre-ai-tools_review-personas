"""Minimal GitHub REST client: the one marker comment (D7) and read-only PR history (D13)."""

from __future__ import annotations

from collections.abc import Iterator

import requests

from .render import MARKER


class GitHub:
    def __init__(self, token: str | None, repo: str, api_url: str = "https://api.github.com"):
        self.repo = repo
        self.api = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def paginate(self, path: str, **params) -> Iterator[dict]:
        url, query = f"{self.api}{path}", {"per_page": 100, **params}
        while url:
            resp = self.session.get(url, params=query, timeout=30)
            resp.raise_for_status()
            yield from resp.json()
            url, query = resp.links.get("next", {}).get("url"), None

    def upsert_comment(self, pr: int, body: str) -> str:
        """Edit the bot's existing marker comment, or create one (COM-2). Returns the action."""
        existing = next(
            (
                c
                for c in self.paginate(f"/repos/{self.repo}/issues/{pr}/comments")
                if (c.get("body") or "").startswith(MARKER)
                and (c.get("user") or {}).get("type") == "Bot"
            ),
            None,
        )
        if existing:
            resp = self.session.patch(
                f"{self.api}/repos/{self.repo}/issues/comments/{existing['id']}",
                json={"body": body},
                timeout=30,
            )
            action = "updated"
        else:
            resp = self.session.post(
                f"{self.api}/repos/{self.repo}/issues/{pr}/comments",
                json={"body": body},
                timeout=30,
            )
            action = "created"
        resp.raise_for_status()
        return action
