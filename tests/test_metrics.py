from datetime import datetime

from review_personas.metrics import compare, report

ALICE, BOB = {"login": "alice", "type": "User"}, {"login": "bob", "type": "User"}
BOT = {"login": "github-actions[bot]", "type": "Bot"}


def pr(n, created, merged=None):
    return {"number": n, "user": ALICE, "created_at": created, "merged_at": merged}


class FakeGitHub:
    repo = "o/r"

    def __init__(self):
        self.data = {
            "/repos/o/r/pulls": [
                pr(4, "2026-11-20T00:00:00Z"),  # after the window: ignored
                pr(3, "2026-11-03T00:00:00Z", "2026-11-03T10:00:00Z"),
                pr(2, "2026-10-20T00:00:00Z", "2026-10-21T00:00:00Z"),
                pr(1, "2026-10-01T00:00:00Z"),  # before the window: stops paging
            ],
            # PR 2: draft until 06:00; bot and author comments don't count; Bob reviews at 08:00
            "/repos/o/r/issues/2/events": [
                {"event": "ready_for_review", "created_at": "2026-10-20T06:00:00Z"}
            ],
            "/repos/o/r/pulls/2/reviews": [
                {"user": BOT, "submitted_at": "2026-10-20T06:05:00Z"},
                {"user": ALICE, "submitted_at": "2026-10-20T06:10:00Z"},
                {"user": BOB, "submitted_at": "2026-10-20T08:00:00Z"},
            ],
            "/repos/o/r/pulls/2/comments": [],
            # PR 3: Bob's review comment after 2 hours
            "/repos/o/r/issues/3/events": [],
            "/repos/o/r/pulls/3/reviews": [],
            "/repos/o/r/pulls/3/comments": [{"user": BOB, "created_at": "2026-11-03T02:00:00Z"}],
        }

    def paginate(self, path, **params):
        yield from self.data[path]


def test_compare_before_after():
    before, after = compare(FakeGitHub(), datetime(2026, 11, 1), weeks=2)
    assert (before.prs, before.first_review_hours, before.merge_hours) == (1, 2.0, 24.0)
    assert (after.prs, after.first_review_hours, after.merge_hours) == (1, 2.0, 10.0)
    text = report(before, after)
    assert "time to merge       24.0h    10.0h    -58%" in text
    assert "first human review  2.0h     2.0h     +0%" in text
