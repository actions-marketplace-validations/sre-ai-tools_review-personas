"""Plan each persona's review, then run the plans against a model (D3, D5, D10)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from .changes import FileChange
from .config import Persona, Settings
from .filtering import NotReviewed, global_filter, persona_diff
from .llm import LLM
from .prompt import PersonaPrompt, build_prompt
from .reply import InvalidReply, Verdict, parse_reply, retry_message
from .result import PersonaResult, Usage

ALL_TOO_LARGE = "Every matching change is over the size limit"
MAX_ERROR_CHARS = 200
# Wall-clock budget for all persona reviews together. Per-call retries alone can run far past
# the 5-minute target (CI-4) and the job timeout, which would kill the job before the comment
# is posted; past this deadline unfinished personas are reported as timed out instead (D8).
REVIEW_DEADLINE_S = 240


@dataclass
class PersonaPlan:
    persona: Persona
    prompt: PersonaPrompt | None = None  # None: no model call needed
    skipped_by_paths: bool = False
    no_changes: bool = False
    error: str | None = None
    not_reviewed: list[NotReviewed] = field(default_factory=list)

    def result(self) -> PersonaResult:
        """The result for a plan that needs no model call."""
        return PersonaResult(
            persona=self.persona,
            verdict=None if self.error or self.skipped_by_paths else Verdict(False),
            error=self.error,
            skipped_by_paths=self.skipped_by_paths,
            not_reviewed=self.not_reviewed,
        )


def plan_reviews(
    settings: Settings, files: list[FileChange], *, title: str, body: str
) -> tuple[list[PersonaPlan], list[NotReviewed]]:
    """Shared by CI and local runs, so both apply identical filtering (LOC-3)."""
    kept, skipped = global_filter(files, settings.sensitive, settings.generated)
    plans = []
    for persona in settings.personas:
        diff = persona_diff(kept, persona.paths, settings.max_diff_chars)
        plan = PersonaPlan(persona, not_reviewed=diff.not_reviewed)
        if diff.files:
            plan.prompt = build_prompt(
                persona, title=title, body=body, diff=diff, not_reviewed=skipped
            )
        elif diff.not_reviewed:
            plan.error = ALL_TOO_LARGE
        elif persona.paths is not None:
            plan.skipped_by_paths = True
        else:
            plan.no_changes = True  # nothing reviewable at all, e.g. only sensitive files
        plans.append(plan)
    return plans, skipped


def short_error(e: BaseException) -> str:
    """Error type and first line only: safe to show in a PR comment (D10)."""
    first = (str(e).strip().splitlines() or [""])[0]
    text = f"{type(e).__name__}: {first}" if first else type(e).__name__
    return text[:MAX_ERROR_CHARS]


def review(plan: PersonaPlan, llm: LLM) -> PersonaResult:
    if plan.prompt is None:
        return plan.result()
    persona = plan.persona
    result = PersonaResult(persona=persona, not_reviewed=plan.not_reviewed, usage=Usage())
    messages = [{"role": "user", "text": plan.prompt.user}]
    started = time.monotonic()
    try:
        for attempt in range(2):  # one retry on an unusable reply (D3)
            completion = llm.complete(
                model=persona.model,
                system=plan.prompt.system,
                messages=messages,
                model_params=persona.model_params,
            )
            result.usage += completion.usage
            try:
                result.verdict = parse_reply(completion.text)
                break
            except InvalidReply as e:
                if completion.stop_reason == "max_tokens":
                    result.error = "Model hit its output token limit"
                    break
                if attempt == 1:
                    result.error = f"Invalid reply after retry: {e}"
                    break
                messages += [
                    {"role": "assistant", "text": completion.text or "(empty)"},
                    {"role": "user", "text": retry_message(e)},
                ]
    except Exception as e:  # noqa: BLE001 - any provider failure becomes a ⚠️ row (COM-4)
        result.error = short_error(e)
    result.seconds = time.monotonic() - started
    return result


def run_plans(
    plans: list[PersonaPlan], llm: LLM, deadline_s: float = REVIEW_DEADLINE_S
) -> list[PersonaResult]:
    """Review in parallel; personas still running at the deadline become ⚠️ timeouts.

    Daemon threads, so a hung provider call can't keep the process alive after we return.
    """
    done: dict[int, PersonaResult] = {}

    def work(i: int, plan: PersonaPlan) -> None:
        done[i] = review(plan, llm)

    threads = [
        threading.Thread(target=work, args=(i, plan), daemon=True) for i, plan in enumerate(plans)
    ]
    for t in threads:
        t.start()
    end = time.monotonic() + deadline_s
    for t in threads:
        t.join(max(0.0, end - time.monotonic()))
    snapshot = dict(done)  # late finishers must not change what we render
    return [
        snapshot.get(i)
        or PersonaResult(
            persona=plan.persona,
            error=f"Timed out after {deadline_s:g}s",
            not_reviewed=plan.not_reviewed,
        )
        for i, plan in enumerate(plans)
    ]


def pipeline_broken(plans: list[PersonaPlan], results: list[PersonaResult]) -> bool:
    """True when every persona that called the model failed (D10: fail the check)."""
    called = [r for p, r in zip(plans, results, strict=True) if p.prompt is not None]
    return bool(called) and all(r.error for r in called)
