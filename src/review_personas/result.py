"""The outcome of one persona's review, shared by CI, local runs, scoring and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Persona
from .filtering import NotReviewed
from .reply import Verdict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens
        )


@dataclass
class PersonaResult:
    persona: Persona
    verdict: Verdict | None = None  # None when the review failed or was skipped by paths
    error: str | None = None
    skipped_by_paths: bool = False
    not_reviewed: list[NotReviewed] = field(default_factory=list)  # size limit, this persona
    usage: Usage | None = None  # None locally: Claude Code doesn't expose subagent usage
    seconds: float = 0.0

    @property
    def scored(self) -> bool:
        return self.verdict is not None and self.verdict.relevant and self.error is None
