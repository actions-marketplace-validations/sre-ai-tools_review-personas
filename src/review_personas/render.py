"""The combined review comment (D7), its cost footer and the job summary table (D9)."""

from __future__ import annotations

import re

from .config import Price
from .filtering import NotReviewed
from .result import PersonaResult, Usage
from .scoring import cumulative_score

MARKER = "<!-- review-personas -->"
SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}

_MD_SPECIAL = re.compile(r"([\\`*_\[\]!|#~])")


def escape(text: str) -> str:
    """Make model text inert: no Markdown, HTML, links, images or @-mentions (REV-5, D7)."""
    text = " ".join(text.split())
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = _MD_SPECIAL.sub(r"\\\1", text)
    text = re.sub(r"(?i)\b(https?|ftp)://", "\\1\u200b://", text)  # no autolinks
    return text.replace("@", "@\u200b")  # no mentions


def _code(text: str) -> str:
    return "`" + " ".join(text.replace("`", "'").split()) + "`"


def _title(r: PersonaResult) -> str:
    return escape(f"{r.persona.icon} {r.persona.name}".strip())


def _tokens(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def persona_cost(r: PersonaResult, prices: dict[str, Price]) -> float | None:
    price = prices.get(r.persona.model)
    if r.usage is None or price is None:
        return None
    return (
        r.usage.input_tokens * price.input_per_mtok + r.usage.output_tokens * price.output_per_mtok
    ) / 1_000_000


def total_usage(results: list[PersonaResult]) -> Usage | None:
    used = [r.usage for r in results if r.usage is not None]
    return sum(used, Usage()) if used else None


def cost_text(results: list[PersonaResult], prices: dict[str, Price]) -> str | None:
    billed = [r for r in results if r.usage is not None and r.usage.input_tokens]
    costs = [persona_cost(r, prices) for r in billed]
    known = [c for c in costs if c is not None]
    if not known:
        return None
    text = f"${sum(known):.2f}"
    return text if len(known) == len(costs) else f"{text} (partial: some models have no price)"


def _row(r: PersonaResult) -> str:
    if r.error:
        return f"| {_title(r)} | ⚠️ | Review failed: {escape(r.error)} |"
    if r.skipped_by_paths:
        return f"| {_title(r)} | – | Not relevant: no matching files |"
    if not r.verdict.relevant:
        return f"| {_title(r)} | – | Not relevant |"
    return f"| {_title(r)} | {r.verdict.score} | {escape(r.verdict.summary)} |"


def _not_reviewed(global_skips: list[NotReviewed], results: list[PersonaResult]) -> list[str]:
    seen, out = set(), []
    for n in [*global_skips, *(n for r in results for n in r.not_reviewed)]:
        if (n.path, n.reason) not in seen:
            seen.add((n.path, n.reason))
            out.append(f"{_code(n.path)} ({n.reason})")
    return out


def comment(
    results: list[PersonaResult],
    *,
    not_reviewed: list[NotReviewed],
    prices: dict[str, Price],
    reviewed: str,
) -> str:
    """`reviewed` describes what was reviewed, e.g. "commit abc1234"."""
    score = cumulative_score(results)
    headline = f"{score}/10 (advisory)" if score is not None else "no score (no relevant reviews)"
    lines = [
        MARKER,
        f"## 🧩 Persona review: {headline}",
        "",
        "| Persona | Score | Summary |",
        "|---|---|---|",
        *(_row(r) for r in results),
    ]
    for r in results:
        if r.scored and r.verdict.findings:
            lines += ["", f"**{_title(r)}**"]
            for f in r.verdict.findings:
                where = f"{f.file}:{f.line}" if f.file and f.line else f.file
                loc = f"{_code(where)} " if where else ""
                lines.append(f"- {SEVERITY_ICON[f.severity]} {loc}{escape(f.comment)}")

    footer = []
    skipped = _not_reviewed(not_reviewed, results)
    if skipped:
        footer.append("Not reviewed: " + ", ".join(skipped) + ".")
    footer.append(f"Reviewed {escape(reviewed)}.")
    usage = total_usage(results)
    if usage is not None:
        tokens = f"Tokens: {_tokens(usage.input_tokens)} in / {_tokens(usage.output_tokens)} out"
        cost = cost_text(results, prices)
        footer.append(tokens + (f", est. {cost}." if cost else "."))
    lines += ["", f"<sub>{' '.join(footer)}</sub>"]
    return "\n".join(lines) + "\n"


def job_summary(results: list[PersonaResult], prices: dict[str, Price]) -> str:
    lines = [
        "### Persona review usage",
        "",
        "| Persona | Model | Input tokens | Output tokens | Est. cost | Seconds |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        u = r.usage or Usage()
        cost = persona_cost(r, prices)
        lines.append(
            f"| {_title(r)} | {_code(r.persona.model)} | {u.input_tokens} | {u.output_tokens} "
            f"| {'' if cost is None else f'${cost:.4f}'} | {r.seconds:.1f} |"
        )
    usage = total_usage(results) or Usage()
    cost = cost_text(results, prices)
    lines.append(f"| **Total** | | {usage.input_tokens} | {usage.output_tokens} | {cost or ''} | |")
    return "\n".join(lines) + "\n"
