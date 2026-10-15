# Requirements: review-personas

> Status: **Approved** by the owner, 2026-10-14. Derived from [intent.md](intent.md) (approved 2026-10-14). These describe *what* the system must do; *how* belongs in design.md.
>
> Each requirement has an ID for traceability (`[I: …]` points to the part of intent.md it comes from). **Must** means required for the pilot; **Should** means wanted, but the pilot can ship without it.

## Personas

- **PER-1 Must.** Four built-in personas: AWS architect, App developer, UI developer, DBA. `[I: What]`
- **PER-2 Must.** Each persona has a name, a focus (what it reviews), and a model. `[I: Customisation]`
- **PER-3 Must.** A caller repo can choose which built-in personas run. By default, all four run. `[I: Customisation]`
- **PER-4 Must.** A caller repo can set the model per persona and a default model for all of them. `[I: Customisation]`
- **PER-5 Must.** A caller repo can add extra focus text to a built-in persona without replacing it. `[I: Customisation]`
- **PER-6 Must.** A caller repo can define new personas with a name and focus. `[I: Customisation]`
- **PER-7 Must.** Invalid persona config fails with a message naming the problem, rather than being silently ignored. _(Derived: callers can't otherwise tell a typo from a working config.)_

## Review behaviour

- **REV-1 Must.** Each persona decides whether the PR touches its area. If not, it reports **Not relevant**, with no score and no findings. `[I: Req 3]`
- **REV-2 Must.** A relevant persona returns a one-sentence summary, a score from 0 to 10, and at most 3 findings. `[I: Succinct]`
- **REV-3 Must.** Each finding is 25 words or fewer, says what to change, and names a file (and a line where possible). No praise or nitpicks. `[I: Succinct]`
- **REV-4 Must.** The limits in REV-2 and REV-3 are enforced by the system, not only requested from the model. _(Derived: models don't always obey length instructions.)_
- **REV-5 Must.** PR titles, descriptions and diffs are treated as untrusted input. Instructions inside them do not change persona behaviour. _(Derived: PR authors control that content.)_

## Scoring

- **SCO-1 Must.** The cumulative score is the average of the relevant personas' scores, shown with one decimal place. `[I: Cumulative score]`
- **SCO-2 Must.** Not-relevant personas, and personas whose review failed, are left out of the average. When none are left, the comment says "no score" instead of showing 0. `[I: Cumulative score]`
- **SCO-3 Must.** The score never blocks a merge: the CI check passes whatever the score. `[I: Gate or advice]`

## PR comment (CI)

- **COM-1 Must.** One combined comment per PR, containing the cumulative score, a one-line row per persona (score or "Not relevant"), then each relevant persona's findings. `[I: Comment shape]`
- **COM-2 Must.** Every push re-reviews the whole PR and replaces the content of that one comment. A second comment is never created. `[I: Re-runs]`
- **COM-3 Must.** Files that were not reviewed are listed in the comment with the reason: sensitive (excluded) or too large for the size limit. `[I: Data handling, Cost]`
- **COM-4 Must.** A persona whose review failed (model error, invalid reply) is shown as failed with a short reason, and the other personas' reviews are still posted. _(Derived.)_

## Data handling

- **DAT-1 Must.** Files matching the sensitive-file deny list are never sent to any model, in CI or locally. `[I: Req 7, Data handling]`
- **DAT-2 Must.** A built-in deny list covers at least: `.env` files, private keys and certificates (`*.pem`, `*.key`, `*.p12`, `*.pfx`), and SSH keys. `[I: Data handling]`
- **DAT-3 Must.** A caller repo can add deny-list patterns. It cannot remove built-in ones. _(Derived: keeps the safety floor.)_
- **DAT-4 Must.** The diff sent to a persona has a size limit. Files beyond the limit are left out whole, never cut mid-file, and are listed per COM-3. `[I: Cost]`

## CI integration

- **CI-1 Must.** Callers use this repo through one reusable GitHub workflow, and need no code of their own beyond a workflow file and optional config. `[I: How callers consume it]`
- **CI-2 Must.** It authenticates to AWS with GitHub OIDC by assuming a caller-supplied IAM role. No long-lived AWS keys. `[I: AWS auth]`
- **CI-3 Must.** All CI model calls go through AWS Bedrock, and any Bedrock model the caller's role can call works. `[I: Models]`
- **CI-4 Must.** The review is posted within 5 minutes of the run starting, for a typical pilot PR (≤ 50 changed files). `[I: Success: before a human picks it up]` _(Confirmed.)_
- **CI-5 Must.** Each run records the input and output tokens per persona and in total, visible in the workflow run log or summary. `[I: Cost]`
- **CI-6 Must.** Callers pin a version, and a breaking change to the workflow inputs or config format needs a new major version. _(Derived: other repos depend on it.)_

## Local runs (Claude Code)

- **LOC-1 Must.** A developer runs `/prpanel:review` in Claude Code to review their branch before opening a PR. `[I: Local: entry point, purpose]`
  _Amended 2026-10-15 by the owner: the command is `/prpanel:review` (plugin `prpanel`, command `review`). It was `/review-personas`, which Claude Code shows as `/review-personas:review-personas`._
- **LOC-2 Must.** By default it reviews the current branch compared with its base branch, including uncommitted changes. `[I: Local: scope]`
- **LOC-3 Must.** It uses the same persona definitions, review rules (REV-\*), scoring (SCO-1, SCO-2) and deny list (DAT-\*) as CI, and the same repo config file. `[I: Local: consistency]`
- **LOC-4 Must.** It uses the developer's own Claude Code session and model, and needs no AWS access. `[I: Req 8]`
- **LOC-5 Must.** The output appears in the Claude Code chat in the same layout as the CI comment. Nothing is posted to GitHub and no files are written. `[I: Local: output]`
- **LOC-6 Must.** Developers install it as a Claude Code plugin from this repo. `[I: Local: entry point]`

## Maintainability

- **MNT-1 Must.** Persona definitions, review rules and the deny list live in one place that both CI and the local plugin read. `[I: Still open: design constraint]`
- **MNT-2 Must.** All provider-specific code sits behind one interface, so adding a provider doesn't change the review logic. `[I: Providers]`
- **MNT-3 Should.** Review quality is checked with an eval set: sample PRs with expected relevance and key findings, re-run whenever prompts, personas or default models change. _(From the playbook's Test stage.)_

## Pilot measurement

- **MEA-1 Should.** For pilot repos, report the median time to first human review and time to merge for the 4 weeks before and after adoption. `[I: Still open: measuring success]` _(Accepted as a Should; where the measurement runs is decided in design.md.)_

## Not required (from intent: out of scope)

- Blocking merges.
- Inline line comments, or separate comments per persona.
- Providers other than Bedrock in CI.
- Local agents other than Claude Code.
- Posting from local runs.
