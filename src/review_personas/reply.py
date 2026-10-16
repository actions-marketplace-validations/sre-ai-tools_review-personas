"""Validate a persona's JSON reply and enforce the succinctness limits in code (D3, REV-4)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

MAX_FINDINGS = 3
MAX_WORDS = 25
SEVERITIES = ("high", "medium", "low")


class InvalidReply(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    severity: str
    comment: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class Verdict:
    relevant: bool
    summary: str = ""
    score: int | None = None
    findings: tuple[Finding, ...] = field(default_factory=tuple)


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]


def _cap_words(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_WORDS]) + ("…" if len(words) > MAX_WORDS else "")


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_reply(text: str) -> Verdict:
    """Raise InvalidReply with a message suitable for sending back to the model."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise InvalidReply("no JSON object found")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise InvalidReply(f"invalid JSON: {e.msg}") from e
    if not isinstance(data, dict) or not isinstance(data.get("relevant"), bool):
        raise InvalidReply('"relevant" must be true or false')

    summary = data.get("summary")
    summary = _first_sentence(summary) if isinstance(summary, str) else ""
    if not data["relevant"]:
        return Verdict(relevant=False, summary=summary)

    score = data.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise InvalidReply('"score" must be a number from 0 to 10 when "relevant" is true')
    if not summary:
        raise InvalidReply('"summary" must be a non-empty sentence when "relevant" is true')
    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        raise InvalidReply('"findings" must be a list')

    findings = []
    for raw in raw_findings:
        if not isinstance(raw, dict) or not isinstance(raw.get("comment"), str):
            continue
        comment = _cap_words(raw["comment"].strip())
        if not comment:
            continue
        severity = str(raw.get("severity", "")).lower()
        file = raw.get("file")
        line = raw.get("line")
        findings.append(
            Finding(
                severity=severity if severity in SEVERITIES else "low",
                comment=comment,
                file=file.strip() or None if isinstance(file, str) else None,
                line=line if _is_int(line) and line > 0 else None,
            )
        )
        if len(findings) == MAX_FINDINGS:
            break
    return Verdict(
        relevant=True,
        summary=summary,
        score=max(0, min(10, round(score))),
        findings=tuple(findings),
    )


def retry_message(error: InvalidReply | str) -> str:
    return (
        f"Your reply could not be used: {error}. "
        "Reply again with only the JSON object in the required shape."
    )
