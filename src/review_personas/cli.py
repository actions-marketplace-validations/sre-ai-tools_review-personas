"""Command line: `review-personas ci | prepare | finish | metrics`. Exit codes follow design D10."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .changes import GitError, ci_changes
from .config import ConfigError, load_settings
from .render import comment, job_summary

EXIT_OK, EXIT_BROKEN, EXIT_CONFIG = 0, 1, 2


def _split(value: str) -> list[str] | None:
    return [s.strip() for s in value.split(",") if s.strip()] or None


def _event() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).is_file():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8")).get("pull_request") or {}


def cmd_ci(args: argparse.Namespace, llm=None, github=None) -> int:
    from .github import GitHub
    from .llm import BedrockLLM
    from .runner import pipeline_broken, plan_reviews, run_plans

    root = Path(args.repo_root)
    try:
        settings = load_settings(
            root,
            args.config,
            model_override=args.model or None,
            personas_override=_split(args.personas),
        )
    except ConfigError as e:
        print(f"::error::review-personas config error: {e}", file=sys.stderr)
        return EXIT_CONFIG

    pr = _event()
    number = args.pr or pr.get("number")
    base = args.base_ref or (f"origin/{pr['base']['ref']}" if pr.get("base") else None)
    head = args.head or (pr.get("head") or {}).get("sha") or "HEAD"
    if not base or (not number and not args.dry_run):
        print("::error::Need a pull_request event or --base-ref and --pr", file=sys.stderr)
        return EXIT_CONFIG
    try:
        files = ci_changes(root, base, head)
    except GitError as e:
        print(f"::error::{e}", file=sys.stderr)
        return EXIT_BROKEN

    plans, skipped = plan_reviews(
        settings, files, title=args.title or pr.get("title") or "", body=pr.get("body") or ""
    )
    results = run_plans(plans, llm or BedrockLLM(args.region))
    body = comment(
        results, not_reviewed=skipped, prices=settings.prices, reviewed=f"commit {head[:7]}"
    )

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(job_summary(results, settings.prices))
    for r in results:
        if r.error:
            print(f"::warning::{r.persona.id}: {r.error}", file=sys.stderr)

    if args.dry_run:
        print(body)
    else:
        try:
            gh = github or GitHub(
                os.environ.get("GITHUB_TOKEN"),
                args.repo or os.environ["GITHUB_REPOSITORY"],
                os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            )
            print(f"Review comment {gh.upsert_comment(int(number), body)}.")
        except Exception as e:  # noqa: BLE001 - D10: comment not postable fails the check
            print(f"::error::Could not post the review comment: {e}", file=sys.stderr)
            return EXIT_BROKEN

    if pipeline_broken(plans, results):
        print("::error::Every persona review failed; see warnings above.", file=sys.stderr)
        return EXIT_BROKEN
    return EXIT_OK  # a low score never fails the check (SCO-3)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="review-personas", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    ci = sub.add_parser("ci", help="Review a pull request with AWS Bedrock and post the comment")
    ci.add_argument("--repo-root", default=".", help="Checkout of the caller repo")
    ci.add_argument("--config", default=None, help="Config path relative to the repo root")
    ci.add_argument("--personas", default="", help="Comma-separated ids to run (overrides config)")
    ci.add_argument("--model", default="", help="Model ID for every persona (overrides config)")
    ci.add_argument("--region", default=None, help="AWS region (default: AWS_REGION)")
    ci.add_argument("--repo", default=None, help="owner/name (default: GITHUB_REPOSITORY)")
    ci.add_argument("--pr", type=int, default=None, help="PR number (default: from the event)")
    ci.add_argument("--base-ref", default=None, help="Base ref (default: origin/<PR base>)")
    ci.add_argument("--head", default=None, help="Head commit (default: PR head SHA, else HEAD)")
    ci.add_argument("--title", default=None, help="PR title (default: from the event)")
    ci.add_argument("--dry-run", action="store_true", help="Print the comment; don't post")
    ci.set_defaults(func=cmd_ci)

    prep = sub.add_parser("prepare", help="Local: write per-persona prompt files (JSON on stdout)")
    prep.add_argument("--repo-root", default=".", help="The repository to review")
    prep.add_argument("--base", default=None, help="Base branch (default: the remote's default)")
    prep.add_argument("--config", default=None, help="Config path relative to the repo root")
    prep.add_argument("--personas", default="", help="Comma-separated ids to run")
    prep.set_defaults(func=cmd_prepare)

    fin = sub.add_parser("finish", help="Local: validate replies and print the review")
    fin.add_argument("dir", help="The directory printed by `prepare`")
    fin.set_defaults(func=cmd_finish)

    met = sub.add_parser("metrics", help="Pilot: median review speed before vs after adoption")
    met.add_argument("--repo", required=True, help="owner/name")
    met.add_argument("--adopted", required=True, help="Adoption date, YYYY-MM-DD")
    met.add_argument("--weeks", type=int, default=4, help="Weeks before and after (default 4)")
    met.set_defaults(func=cmd_metrics)
    return p


def cmd_metrics(args: argparse.Namespace, github=None) -> int:
    from datetime import datetime

    from .github import GitHub
    from .metrics import compare, report

    try:
        adopted = datetime.fromisoformat(args.adopted)
    except ValueError:
        print(
            f"review-personas: --adopted must be a date like 2026-11-01, got {args.adopted!r}",
            file=sys.stderr,
        )
        return EXIT_CONFIG
    if args.weeks < 1:
        print("review-personas: --weeks must be at least 1", file=sys.stderr)
        return EXIT_CONFIG
    gh = github or GitHub(
        os.environ.get("GITHUB_TOKEN"),
        args.repo,
        os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    try:
        before, after = compare(gh, adopted, args.weeks)
    except Exception as e:  # noqa: BLE001 - network/API errors: one clear line, no traceback
        print(f"review-personas: could not read PR history for {args.repo}: {e}", file=sys.stderr)
        return EXIT_BROKEN
    print(report(before, after), end="")
    return EXIT_OK


def cmd_prepare(args: argparse.Namespace) -> int:
    from .local import prepare

    try:
        out = prepare(
            Path(args.repo_root),
            base=args.base,
            config=args.config,
            personas=_split(args.personas),
        )
    except (ConfigError, GitError) as e:
        print(f"review-personas: {e}", file=sys.stderr)
        return EXIT_CONFIG
    print(json.dumps(out, indent=2))
    return EXIT_OK


EXIT_RETRY = 3


def cmd_finish(args: argparse.Namespace) -> int:
    from .local import finish

    try:
        out = finish(Path(args.dir))
    except (OSError, ValueError, KeyError, TypeError) as e:
        # Missing or damaged working directory, e.g. already finished or never prepared.
        print(
            f"review-personas: cannot finish {args.dir}: {type(e).__name__}: {e}. "
            "Run `review-personas prepare` again.",
            file=sys.stderr,
        )
        return EXIT_CONFIG
    if "retry" in out:
        print(json.dumps(out, indent=2))
        return EXIT_RETRY
    print(out["review"])
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
