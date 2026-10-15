# Intent: test applications

> Status: **Approved** by the owner, 2026-10-15.

## What

Test applications that review-personas can be pointed at, the way a real caller repo would use it. Each one is a small but realistic codebase, with a set of prepared pull requests whose expected review outcome is known in advance.

They are used to verify change 0001 end to end, before the pilot and after each release:

- **CI path:** a caller repo runs the reusable workflow (`review.yml`) with GitHub OIDC and Bedrock, and gets one combined PR comment.
- **Local path:** a developer runs `/prpanel:review` on a branch of the test application.

## Why

**0001 is built but not verified end to end.** The unit tests use no network, and the evals score review quality on fixed diffs. Neither one exercises what a caller actually depends on:

- `workflow_call` from another repo;
- OIDC role assumption;
- checkout and merge-base on a real PR;
- the comment being edited in place on re-push;
- caller config and custom personas;
- the plugin installed in another repo.

Test applications close that gap. They also show new adopters what a working setup looks like.

## Who uses it

- The owner, to verify 0001 before the pilot and each release before it is tagged.
- Pilot adopters, as a reference caller setup to copy.

## Requirements

1. The test application touches every built-in persona's area:
   - AWS infrastructure;
   - application code;
   - UI;
   - database schema and queries.
2. The test application is set up as a caller: it has the caller workflow, `.github/review-personas.yml` and at least one custom persona.
3. A set of **prepared PRs** (scenarios), each with a written expected outcome. Examples:
   - a clean change;
   - one seeded issue per persona;
   - docs-only, so every persona is not relevant;
   - a sensitive file;
   - a prompt-injection attempt;
   - an oversize change;
   - a re-push, so the same comment is updated;
   - a per-persona model override.
4. Each scenario can be run on both paths, CI and local, and the result checked against its expected outcome.
5. Scenarios can be reset and re-run, so a release can be verified again without hand-editing the app.

## Decisions

_Confirmed by the owner, 2026-10-15._

| Decision | Choice |
|---|---|
| Where the test app lives | **A separate repo, `sre-ai-tools/review-personas-testbed`.** The caller path (`workflow_call`, OIDC, plugin install) can only be tested from another repo. |
| How many apps | **One polyglot app**, so all four personas have something to review in one place. |
| Stack | **Terraform** for AWS, a **Python** API, a **React** UI and **Postgres** SQL migrations. |
| Must the app run? | **No.** It only needs to look real to a reviewer. Nothing is built, tested or deployed. |
| How scenarios are created | **A script** creates or resets each scenario branch and opens its PR, from a patch stored in the testbed repo with the scenario's expected outcome. |
| Who checks the outcome | **The owner, using each scenario's expected outcome as a checklist.** An automated checker is left for a later change. |
| When scenarios run | **Only when the owner triggers them**, because Bedrock calls cost money. They don't run on a schedule or as a required release step. |
| Relation to evals | **The testbed complements the evals.** Evals measure review quality; the testbed verifies integration. Seeded issues may be adapted from eval cases. |

## Out of scope

- Deploying or running the test applications.
- Measuring pilot success (MEA-1). That needs real repos and real reviewers.
- Changing review-personas itself. Bugs found here are fixed under 0001 or a new change.
- Load or scale testing beyond the pilot's size.

## Success looks like

- Every scenario has run on both paths, and each result matches its expected outcome or has a filed fix.
- 0001's status in the specs index can move from "awaiting end-to-end verification" to verified.
- A new release can be re-verified in under an hour.

## Still open

- **AWS account and IAM role** for the testbed's OIDC access to Bedrock. To be decided in design.md.
