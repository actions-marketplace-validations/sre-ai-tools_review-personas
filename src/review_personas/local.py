"""Local runs through Claude Code (D1, LOC-*): `prepare` writes per-persona prompt files,
Claude Code subagents write replies, `finish` validates, scores and prints the review.

Everything lives in a temporary directory outside the repo, deleted by the final `finish`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from .changes import git, local_changes
from .config import Persona, load_settings
from .filtering import NotReviewed
from .render import comment
from .reply import InvalidReply, parse_reply, retry_message
from .result import PersonaResult
from .runner import PersonaPlan, plan_reviews

MANIFEST = "manifest.json"
PROMPT_FILE = "prompts/{id}.md"
REPLY_FILE = "replies/{id}.txt"


def prompt_file_text(system: str, user: str) -> str:
    return f"<instructions>\n{system}\n</instructions>\n\n{user}\n"


def prepare(
    repo_root: Path,
    *,
    base: str | None = None,
    config: str | None = None,
    personas: list[str] | None = None,
    out_dir: Path | None = None,
) -> dict:
    settings = load_settings(repo_root, config, personas_override=personas)
    files, base_used = local_changes(repo_root, base)
    branch = git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    last_commit = git(repo_root, "log", "-1", "--format=%s").strip() if files else ""
    plans, skipped = plan_reviews(settings, files, title=f"{branch}: {last_commit}", body="")

    work = out_dir or Path(tempfile.mkdtemp(prefix="review-personas-"))
    (work / "prompts").mkdir(parents=True, exist_ok=True)
    (work / "replies").mkdir(exist_ok=True)
    entries = []
    for plan in plans:
        entry = {
            "persona": asdict(plan.persona),
            "prompt_file": None,
            "skipped_by_paths": plan.skipped_by_paths,
            "no_changes": plan.no_changes,
            "error": plan.error,
            "not_reviewed": [asdict(n) for n in plan.not_reviewed],
        }
        if plan.prompt:
            path = work / PROMPT_FILE.format(id=plan.persona.id)
            path.write_text(prompt_file_text(plan.prompt.system, plan.prompt.user), "utf-8")
            entry["prompt_file"] = str(path)
            entry["reply_file"] = str(work / REPLY_FILE.format(id=plan.persona.id))
        entries.append(entry)
    manifest = {
        "dir": str(work),
        "reviewed": f"branch {branch} vs {base_used}, including uncommitted changes",
        "not_reviewed": [asdict(n) for n in skipped],
        "personas": entries,
        "retried": False,
    }
    (work / MANIFEST).write_text(json.dumps(manifest, indent=2), "utf-8")
    return {
        "dir": str(work),
        "reviewed": manifest["reviewed"],
        "changed_files": len(files),
        "reviews": [
            {
                "id": e["persona"]["id"],
                "prompt_file": e["prompt_file"],
                "reply_file": e["reply_file"],
            }
            for e in entries
            if e["prompt_file"]
        ],
    }


def _plan(entry: dict) -> PersonaPlan:
    p = entry["persona"]
    persona = Persona(**{**p, "paths": tuple(p["paths"]) if p["paths"] is not None else None})
    return PersonaPlan(
        persona=persona,
        skipped_by_paths=entry["skipped_by_paths"],
        no_changes=entry["no_changes"],
        error=entry["error"],
        not_reviewed=[NotReviewed(**n) for n in entry["not_reviewed"]],
    )


def finish(work: Path) -> dict:
    """Returns {"retry": [...]} once if any reply is unusable, else {"review": markdown}.

    The final call deletes the working directory (LOC-5: nothing left behind).
    """
    manifest = json.loads((work / MANIFEST).read_text("utf-8"))
    results, retry = [], []
    for entry in manifest["personas"]:
        plan = _plan(entry)
        if not entry["prompt_file"]:
            results.append(plan.result())
            continue
        result = PersonaResult(persona=plan.persona, not_reviewed=plan.not_reviewed)
        reply_path = Path(entry["reply_file"])
        try:
            if not reply_path.is_file():
                raise InvalidReply("no reply was saved")
            result.verdict = parse_reply(reply_path.read_text("utf-8"))
        except InvalidReply as e:
            if not manifest["retried"]:
                retry.append(
                    {
                        "id": plan.persona.id,
                        "prompt_file": entry["prompt_file"],
                        "reply_file": entry["reply_file"],
                        "message": retry_message(e),
                    }
                )
            result.error = f"Invalid reply after retry: {e}"
        results.append(result)

    if retry:
        manifest["retried"] = True
        (work / MANIFEST).write_text(json.dumps(manifest, indent=2), "utf-8")
        return {"retry": retry}

    review = comment(
        results,
        not_reviewed=[NotReviewed(**n) for n in manifest["not_reviewed"]],
        prices={},
        reviewed=manifest["reviewed"],
    )
    shutil.rmtree(work, ignore_errors=True)
    return {"review": review}
