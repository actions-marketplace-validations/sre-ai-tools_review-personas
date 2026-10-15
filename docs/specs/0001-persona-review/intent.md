# Intent: review-personas

> Status: **Approved** by the owner, 2026-10-14.

## What

An AI review pipeline for GitHub pull requests. Several reviewer personas each review a PR, and their reviews appear together in one PR comment with a cumulative score.

Starting personas:

- AWS architect
- App developer
- UI developer
- DBA

## Why

**Faster human review.** PRs wait in review queues. If every PR arrives with a short specialist pre-review, human reviewers start from it: they see at a glance where the risk is and spend their time on what matters, so PRs wait less.

The pipeline supports human reviewers; it does not replace them.

## Who uses it

Other GitHub repositories. They call this repo's reusable workflow from their own pipelines.

## Requirements

1. Each persona reviews the PR. All the reviews appear together in **one combined PR comment**.
2. The PR gets a cumulative score built from the persona reviews. The score is **advisory** and never blocks a merge.
3. A persona whose area the PR doesn't touch says it is **not relevant**, for example the DBA persona on a PR with no database code.
4. AI responses are succinct.
5. The caller can customise both the personas and the models.
6. AI calls go through AWS Bedrock first.
7. Sensitive files are never sent to the model.
8. A developer can run the personas **locally** before opening a PR, using an AI agent they already have instead of Bedrock. Fixing issues before the PR exists makes the human review faster too.

## Decisions

| Decision | Choice |
|---|---|
| Language | Python |
| Models | Any Bedrock model, not only Claude |
| How callers consume it | Reusable GitHub workflow |
| Cumulative score | Average of the relevant personas' scores |
| Gate or advice | Advisory only. The score informs the human reviewer and never blocks a merge; the check always passes. |
| Comment shape | One combined PR comment: the cumulative score, a one-line row per persona, then each persona's findings. Not-relevant personas appear as a "Not relevant" row. |
| Succinct | Per persona: a one-sentence summary and at most 3 findings, each 25 words or fewer and saying what to change. No praise or nitpicks. |
| Customisation | Callers choose which built-in personas run, change each persona's model, add extra focus text to a built-in (e.g. "we use Postgres 16"), and define their own personas. |
| Re-runs | Every push re-reviews the whole PR and replaces the content of the one combined comment. Never a second comment. |
| Scale | Pilot: 1–5 repos, tens of PRs a day at most, in the first few months. |
| Cost | No hard cap. Each review records the tokens used, so cost can be tracked. The diff size sent per persona is still bounded. |
| AWS auth | GitHub OIDC: each caller repo assumes an IAM role. No long-lived AWS keys. |
| Data handling | Sensitive files are never sent to the model. A built-in deny list (e.g. `.env`, keys, certificates) is extended by each caller's own patterns. Excluded files are named in the comment as not reviewed. No region restriction. |
| Providers | Bedrock only for now, behind one small provider interface so another provider can be added later without touching the review logic. |
| Local: purpose | Self-review before opening a PR. |
| Local: agent | Claude Code only, for now. |
| Local: entry point | A `/review-personas` slash command, shipped as a Claude Code plugin from this repo. |
| Local: scope | The branch compared with its base branch, including uncommitted changes: what the PR will contain. |
| Local: consistency | The same persona definitions and the same repo config (`.github/review-personas.yml`: personas, extra focus, exclusions) as CI. Only the model differs, so results are close to CI's but not identical. |
| Local: output | Shown in the Claude Code chat only. Nothing is posted to GitHub and no files are written. |

## Out of scope (follows from the decisions)

- Blocking merges based on the score.
- Inline comments on specific lines, and separate comments per persona.
- Providers other than Bedrock in CI, for now.
- Local agents other than Claude Code (Codex, Gemini CLI, Copilot), for now.
- Posting to GitHub from a local run.

## Success looks like

_Confirmed by the owner:_

- The persona review is posted before a human picks up the PR, so it has to finish within minutes of the PR opening or updating.
- Human reviewers read the review and find it useful: short enough to scan in under a minute, with few false alarms.
- Time from a PR opening to merge goes down on repos that adopt it.

## Still open


- **Design constraint from local runs (for Stage 2).** Persona definitions, the review rules (succinct, not relevant) and the sensitive-file exclusions must live in one place that both the Python CI pipeline and the Claude Code plugin read. Otherwise local and CI reviews drift apart.
- **Measuring success.** How do we measure "faster review" in the pilot, and against what baseline? For example, compare median time-to-first-review and time-to-merge for the 4 weeks before and after adoption.
