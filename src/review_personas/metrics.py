"""Pilot measurement (D13, MEA-1): median review speed before vs after adoption. Read-only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


@dataclass
class PrTimes:
    number: int
    opened: datetime
    first_human_review_hours: float | None
    merge_hours: float | None


@dataclass
class Window:
    prs: int
    first_review_hours: float | None
    merge_hours: float | None


def _is_human(user: dict | None, author: str) -> bool:
    user = user or {}
    return user.get("type") != "Bot" and user.get("login") not in (None, author)


def pr_times(gh, pr: dict) -> PrTimes:
    """First human review: from opening, or leaving draft, to the first review or review
    comment by someone other than the author and not a bot. Merge: from opening to merge."""
    n, author = pr["number"], (pr.get("user") or {}).get("login")
    opened = _ts(pr["created_at"])
    ready = [
        _ts(e["created_at"])
        for e in gh.paginate(f"/repos/{gh.repo}/issues/{n}/events")
        if e.get("event") == "ready_for_review"
    ]
    start = max(ready) if ready else opened
    reviews = [
        _ts(r.get("submitted_at"))
        for r in gh.paginate(f"/repos/{gh.repo}/pulls/{n}/reviews")
        if _is_human(r.get("user"), author) and r.get("submitted_at")
    ]
    comments = [
        _ts(c["created_at"])
        for c in gh.paginate(f"/repos/{gh.repo}/pulls/{n}/comments")
        if _is_human(c.get("user"), author)
    ]
    after_start = [t for t in reviews + comments if t >= start]
    merged = _ts(pr.get("merged_at"))
    return PrTimes(
        number=n,
        opened=opened,
        first_human_review_hours=(min(after_start) - start).total_seconds() / 3600
        if after_start
        else None,
        merge_hours=(merged - opened).total_seconds() / 3600 if merged else None,
    )


def _window(times: list[PrTimes]) -> Window:
    reviews = [t.first_human_review_hours for t in times if t.first_human_review_hours is not None]
    merges = [t.merge_hours for t in times if t.merge_hours is not None]
    return Window(
        prs=len(times),
        first_review_hours=median(reviews) if reviews else None,
        merge_hours=median(merges) if merges else None,
    )


def compare(gh, adopted: datetime, weeks: int = 4) -> tuple[Window, Window]:
    adopted = adopted if adopted.tzinfo else adopted.replace(tzinfo=timezone.utc)
    start, end = adopted - timedelta(weeks=weeks), adopted + timedelta(weeks=weeks)
    before, after = [], []
    for pr in gh.paginate(f"/repos/{gh.repo}/pulls", state="all", sort="created", direction="desc"):
        opened = _ts(pr["created_at"])
        if opened < start:
            break  # sorted newest first
        if opened >= end:
            continue
        (before if opened < adopted else after).append(pr_times(gh, pr))
    return _window(before), _window(after)


def report(before: Window, after: Window) -> str:
    def h(v):
        return "–" if v is None else f"{v:.1f}h"

    def change(b, a):
        return "" if b in (None, 0) or a is None else f"{(a - b) / b:+.0%}"

    rows = [
        ("", "before", "after", "change"),
        ("PRs", str(before.prs), str(after.prs), ""),
        (
            "first human review",
            h(before.first_review_hours),
            h(after.first_review_hours),
            change(before.first_review_hours, after.first_review_hours),
        ),
        (
            "time to merge",
            h(before.merge_hours),
            h(after.merge_hours),
            change(before.merge_hours, after.merge_hours),
        ),
    ]
    return "\n".join(f"{a:<20}{b:<9}{c:<9}{d}".rstrip() for a, b, c, d in rows) + "\n"
