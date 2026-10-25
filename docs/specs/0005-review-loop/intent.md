# Intent: review loop

> Status: **Draft**, 2026-10-24. Awaiting owner approval.

## What

A second local command in the `prpanel` plugin, `/prpanel:review-loop`, that runs review → verify → fix → test → review again, up to a set number of rounds, before a PR is opened:

```
/prpanel:review-loop              # up to 2 rounds
/prpanel:review-loop 3 --personas dba,app-developer
```

Each round:

1. **Review** the branch with the same panel, rules and config as `/prpanel:review` (0001 LOC-3).
2. **Verify** each finding against the code: valid, false, or valid but deferred.
3. **Ask** the developer which valid findings to fix.
4. **Fix** those, each with a test that fails without the fix where a test is possible.
5. **Run the tests**, then start the next round.

It stops when a round finds nothing new worth fixing, or after the set number of rounds. It ends with the last review, a list of what was fixed, and a "Known follow-ups" section for the PR description.

## Why

**`/prpanel:review` finds problems; developers then fix them by hand and re-run it, with nothing tying the rounds together.** In the [acme-app](https://github.com/sre-ai-tools/acme-app) demo, that informal loop is where the panel paid off: running it before each PR caught RDS Proxy session pinning, a stale-response race, a CSP wildcard and an expired-token bug, all fixed with tests before the PR existed. The same demo showed what the loop needs to be safe and useful:

- **Findings are sometimes wrong, even from a strong model.** Fixing every finding adds noise; with a weaker model it would have undone a correct fix. Each finding needs checking against the code first.
- **The score is a poor stop signal.** Across five PRs, scores moved between −0.3 and +0.5 after real fixes, because each fix adds new code that is reviewed too. Findings, not the number, show progress.
- **Settled findings come back.** Deferred and rejected findings were raised again in the next round unless something remembered the decision.
- **Fixes need proof.** "Fixed" should mean a test fails when the fix is removed, not that the reviewer stopped mentioning it.

## Who uses it

Developers using the `prpanel` plugin in Claude Code, before opening a PR. CI is unchanged.

## Requirements

1. One command, `/prpanel:review-loop [rounds] [same options as /prpanel:review]`.
2. Each round reviews with the same personas, rules, deny list, limits and scoring as `/prpanel:review`.
3. Every finding is checked against the code and given a verdict, with a one-line reason, before anything is changed.
4. The developer chooses which valid findings are fixed in each round. Nothing is fixed without that choice.
5. Each fix comes with a test that fails without it, where a test is possible; where not, the round says so.
6. The project's tests run after the fixes; a failing run stops the loop and reports it.
7. A finding already rejected or deferred is not proposed again in a later round.
8. The loop stops when a round has no new valid finding at high or medium severity, when the round limit is reached, or when the developer stops it.
9. The score is shown each round but is never used to decide whether to continue.
10. At the end it prints the last review, what each round fixed, and a "Known follow-ups" section listing deferred findings, ready for the PR description.
11. Nothing is posted to GitHub.

## Decisions

_Proposed; to be confirmed by the owner._

| Decision | Proposal |
|---|---|
| Where it lives | **A new command in the `prpanel` plugin** (`commands/review-loop.md`), beside `review`. Same plugin version, same personas. |
| Default and maximum rounds | **2 by default, at most 5.** In the demo, rounds after the second mostly reviewed the previous round's fixes. |
| Who verifies findings | **The developer's Claude Code session**, reading the code; the persona subagents only review, as in 0001 D1. |
| Human in the loop | **Always, in v1.** The developer picks the fixes each round. No unattended mode. |
| Writes to the repo | **Yes, unlike `/prpanel:review`:** it edits code and tests. It does not commit or push; the developer does. |
| Memory between rounds | **In the run's temp directory only**, not in the repo. Persistent "won't fix" decisions belong in the caller's `extra_focus`, which the final report suggests. |

## Open questions

1. Should each round be committed (one commit per round, easy to review and revert), or left uncommitted for the developer?
2. Should a later version offer an unattended mode for findings verified as valid at high severity?
3. Does verification need its own guard against prompt injection in the PR diff, as REV-5 does for reviews?
