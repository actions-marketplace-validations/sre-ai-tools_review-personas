# Requirements: test applications

> Status: **Approved** by the owner, 2026-10-15. Derived from [intent.md](intent.md) (approved 2026-10-15). These describe *what* the testbed must do; *how* belongs in design.md.
>
> Each requirement has an ID for traceability. `[I: …]` points to the part of intent.md it comes from, and `[0001: …]` names the 0001 requirements it verifies. **Must** means required to verify 0001 end to end; **Should** means wanted, but verification can go ahead without it.

## Test application

- **APP-1 Must.** One application in `sre-ai-tools/review-personas-testbed`. It has Terraform for AWS, a Python API, a React UI and Postgres SQL migrations, so every built-in persona has code in its area. `[I: Decisions: location, app count, stack; Req 1]`
- **APP-2 Must.** The code looks like a small real service to a reviewer: consistent names, plausible features, and parts that reference each other (for example, the API reads tables that the migrations create). `[I: Must the app run?]`
- **APP-3 Must.** The app is not built, tested or deployed, and the testbed repo runs no workflows other than the review. `[I: Must the app run?; Out of scope]`
- **APP-4 Must.** The `main` branch has no seeded issues. Issues exist only in scenario patches, so each scenario's expected outcome depends on that scenario alone. _(Derived: otherwise every PR would pick up unrelated findings.)_
- **APP-5 Must.** Secrets in the repo are fake and clearly marked as fake, including those in the sensitive-file scenario. _(Derived: that scenario commits a `.env` file.)_

## Caller setup

- **CAL-1 Must.** The testbed is set up the same way a pilot repo would be: a caller workflow that uses `review.yml`, plus `.github/review-personas.yml`. `[I: Req 2]` `[0001: CI-1]`
- **CAL-2 Must.** The config defines at least one custom persona and adds extra focus to at least one built-in persona. `[I: Req 2]` `[0001: PER-5, PER-6]`
- **CAL-3 Must.** The workflow authenticates to Bedrock with GitHub OIDC. The repo stores no long-lived AWS keys. `[I: Still open: AWS role]` `[0001: CI-2]`
- **CAL-4 Must.** The owner can point the testbed at the review-personas version under test, whether that's a release tag, a branch or a commit. The whole run then uses that version, for both the reusable workflow and the action it calls. _(Derived: `review.yml` calls the action at `@main` until the release job rewrites that ref. Without this requirement, a branch under test would run `main`'s action.)_ `[0001: CI-6]`
- **CAL-5 Should.** The testbed README explains the caller setup well enough for a pilot adopter to copy it. `[I: Who uses it]`

## Scenarios

- **SCN-1 Must.** Each scenario is a patch against `main` plus an expected-outcome file. Both are stored in the testbed repo. `[I: How scenarios are created]`
- **SCN-2 Must.** An expected outcome states only what a correct review must show:
  - which personas are relevant and which are not;
  - the issue each relevant persona must catch, if there is one;
  - which files must be listed as not reviewed, and why;
  - how many comments the PR has;
  - whether the check passes.

  It does not state exact scores or wording. _(Derived: model output varies from run to run.)_ `[I: Who checks the outcome]`
- **SCN-3 Must.** The scenarios cover at least the cases below. Each one verifies the 0001 requirements in brackets.

  | ID | Scenario | Expected outcome | Verifies |
  |---|---|---|---|
  | S1 | Clean change touching all four areas | All four built-ins and the custom persona are relevant; a score is posted; the comment arrives within 5 minutes | COM-1, SCO-1, CI-4, CI-5 |
  | S2 | AWS issue (e.g. SSH open to 0.0.0.0/0) | AWS architect catches it; UI and DBA are not relevant | REV-1, REV-2, REV-3 |
  | S3 | App issue (e.g. missing `None` check) | App developer catches it; AWS and UI are not relevant | REV-1, REV-2, REV-3 |
  | S4 | UI issue (e.g. accessibility) | UI developer catches it; AWS and DBA are not relevant | REV-1, REV-2, REV-3 |
  | S5 | DB issue (e.g. locking migration) | DBA catches it; UI is not relevant | REV-1, REV-2, REV-3 |
  | S6 | Docs-only change | Every persona is not relevant; the comment says "no score" | REV-1, SCO-2 |
  | S7 | Sensitive files: a `.env` file and a file matching a caller deny pattern | Neither is sent to a model; both are listed as not reviewed (sensitive) | DAT-1, DAT-2, DAT-3, COM-3 |
  | S8 | Prompt injection in the PR description and in a code comment | Personas ignore the injected instructions | REV-5 |
  | S9 | Oversize change | Files over the size limit are left out whole and listed as not reviewed (too large) | DAT-4, COM-3 |
  | S10 | Re-push to an open scenario PR | The same comment is updated; no second comment is created | COM-2 |
  | S11 | Config overrides: persona selection and a per-persona model | Only the selected personas run, each on its configured model | PER-3, PER-4 |
  | S12 | One persona set to a model that doesn't exist | That persona is shown as failed; the others are posted; the check passes | COM-4, SCO-2, SCO-3 |
  | S13 | Invalid config (e.g. a typo in a key) | The run fails with a message naming the problem (exit code 2) | PER-7 |

- **SCN-4 Should.** Seeded issues reuse this repo's eval cases where one fits (S2–S5, S8), so the two can be compared. `[I: Relation to evals]`

## Running scenarios

- **RUN-1 Must.** A script creates or resets a scenario's branch from its patch and opens the scenario's PR. The owner can run it for one scenario or for all of them. `[I: How scenarios are created; Req 5]`
- **RUN-2 Must.** Re-running a scenario starts from the same state every time, with no hand-editing of the app or the PR. `[I: Req 5]`
- **RUN-3 Must.** Reviews run only when the owner starts them. Nothing runs on a schedule, and nothing in this repo triggers the testbed. `[I: When scenarios run]`
- **RUN-4 Must.** Every scenario except S10, S12 and S13 can also be run locally: the owner checks out the scenario branch and runs `/prpanel:review`, with the plugin installed from the version under test. `[I: Req 4]` `[0001: LOC-1, LOC-2, LOC-6]`
  _Amendment (owner, 2026-10-15): the script can also run the local path unattended, with `/prpanel:review` in Claude Code's headless mode, so it uses the owner's Claude login and makes no Bedrock call. The owner still checks the results (CHK-1). See design T7._
- **RUN-5 Must.** On the local path, the expected outcome's relevance, not-reviewed files and seeded-issue checks hold just as they do in CI. Nothing is posted to GitHub, and no files are written in the testbed. `[I: Req 4]` `[0001: LOC-3, LOC-4, LOC-5]`

## Checking and recording results

- **CHK-1 Must.** The owner checks each run against the scenario's expected outcome, which serves as the checklist. `[I: Who checks the outcome]`
- **CHK-2 Must.** Each verification run is recorded: the review-personas version, the date, and pass/fail per scenario and per path. Each failure links to a filed fix. `[I: Success looks like]`
- **CHK-3 Should.** Re-verifying a release on both paths takes the owner under an hour. `[I: Success looks like]`

## Not required (from intent: out of scope)

- Building, testing or deploying the app.
- An automated checker for scenario outcomes.
- Scheduled runs, or a required release step.
- Pilot success measurement (0001 MEA-1).
- Changes to review-personas itself. Bugs go to 0001 or a new change.
- Load or scale testing.

## Still open

- **Repo visibility.** Should the testbed be private or public? It contains fake secrets and prompt-injection text on purpose. Public makes it easier for adopters to copy (CAL-5).
- **AWS account and IAM role** for CAL-3. Carried over from intent; to be decided in design.md.
