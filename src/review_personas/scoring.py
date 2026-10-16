"""Cumulative score: plain average of relevant, successful personas (SCO-1, SCO-2)."""

from __future__ import annotations

from .result import PersonaResult


def cumulative_score(results: list[PersonaResult]) -> float | None:
    scores = [r.verdict.score for r in results if r.scored]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)
