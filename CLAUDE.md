# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Process

This repo follows the AI-native SDLC (see [docs/specs/README.md](docs/specs/README.md)). For each change:

1. intent.md
2. requirements.md
3. design.md

Each must be approved by the owner before the next one starts, and no code is written until the design is approved. A new change gets a new numbered folder under `docs/specs/`. Requirement and decision IDs (e.g. `REV-4`, `D7`) are cited in code comments and tests; keep them accurate.

## Commands

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]"   # system Python is 3.9, too old
.venv/bin/pytest                                   # all unit tests (no network)
.venv/bin/pytest tests/test_reply.py -k limits     # single test
.venv/bin/ruff check . && .venv/bin/ruff format .  # CI also runs format --check
```

These call Bedrock and cost money, so ask the owner first:
- `.venv/bin/review-personas ci --base-ref main --dry-run`
- `.venv/bin/python evals/run.py`

## Architecture

One Python core, `src/review_personas/`, serves both CI and local runs (D1). Only the model call differs between them.

- **Plan:** `runner.plan_reviews` does the shared work:
  - `changes` collects the changes with `git diff`;
  - `filtering` removes sensitive, generated and binary files, applies persona `paths` and the whole-file size budget;
  - `prompt.build_prompt` builds each persona's prompt.
- **CI** (`cli.cmd_ci`):
  - plan;
  - `runner.run_plans` with `llm.BedrockLLM` (parallel, one retry);
  - `render.comment`;
  - `github.upsert_comment` edits the single comment that starts with `<!-- review-personas -->`.
- **Local** (`local.py`): the `/review-personas` command (`commands/`, `agents/`) runs `review-personas prepare`, which writes the prompt files to a temp dir. One `persona-reviewer` subagent per persona writes its reply. `review-personas finish` then validates the replies with the same `reply.parse_reply`, scores them and renders the same Markdown. Exit code 3 asks for one retry round.
- **Plugin layout:** the repo root is the Claude Code plugin (`.claude-plugin/`), so `uvx --from "${CLAUDE_PLUGIN_ROOT}"` builds this exact version.
- **Built-in personas:** they live only in `src/review_personas/personas/*.md`, as package data. Custom personas come from the caller's `.github/review-personas/personas/`.

## Invariants

- **Provider code:** boto3 is used only in `llm.py` (MNT-2). Never send `temperature` or `top_p`, because newer Claude models reject them. Model-specific options go through `model_params`.
- **Prompt rules:** the template is in `prompt.py`. Persona files supply only the focus. PR content goes inside tags it cannot close (REV-5). Any change here triggers the evals workflow.
- **Limits:** 3 findings, 25 words and a one-sentence summary are enforced in `reply.py`, not only requested in the prompt (REV-4).
- **Escaping:** model text is escaped in `render.escape`, so it can't produce links, HTML, images or @-mentions.
- **Exit codes (D10):** 0 for OK; 1 when every called persona failed or the comment couldn't be posted; 2 for config errors. A low score never fails.
- **Public interface:** workflow inputs, action inputs, config keys (`config.TOP_LEVEL_KEYS`, `PERSONA_KEYS`) and persona frontmatter keys are used by other repos. Breaking changes need a new major version.
- **Release ref:** `review.yml`'s `uses: sre-ai-tools/review-personas@…` is rewritten by `release.yml`. Keep that line's format.
