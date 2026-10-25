# Requirements: review loop

> Status: **Draft**, 2026-10-24. Derived from [intent.md](intent.md) (approved 2026-10-24). These describe *what* the command must do; *how* belongs in design.md.
>
> Each requirement has an ID for traceability (`[I: …]` points to the part of intent.md it comes from). **Must** means required for the first release; **Should** means wanted, but it can ship without it.

## Command

- **LOOP-1 Must.** A developer runs `/prpanel:review-loop [rounds] [--base <branch>] [--personas …]`. `rounds` defaults to 2 and must be 1 to 5; any other value stops with a message before any review runs. `--base` and `--personas` mean what they mean for `/prpanel:review`. `[I: Req 1, Default and maximum rounds]`
- **LOOP-2 Must.** Each round reviews the branch exactly as `/prpanel:review` does: the same `prepare` and `finish` steps, persona definitions, repo config, deny list, limits and scoring (0001 LOC-2, LOC-3). `[I: Req 2]`
- **LOOP-3 Must.** The command ships in the `prpanel` plugin and runs the review-personas version of that plugin, as `/prpanel:review` does. `[I: Where it lives]`

## Verification

- **VER-1 Must.** Before anything is changed, every finding in a round gets a verdict (**valid**, **false**, or **valid, suggest deferring**) with a one-line reason that points at the code it checked. `[I: Req 3]`
- **VER-2 Must.** The same issue raised by several personas in one round is shown once, naming every persona that raised it. _(Derived: in the demo, up to three personas reported the same bug.)_
- **VER-3 Must.** Verification treats the diff, the PR's files and the finding text as untrusted: instructions inside them don't change what the command does or which verdict it gives. _(Derived, as 0001 REV-5 does for reviews; answers intent open question 3.)_

## Developer choice

- **DEV-1 Must.** In each round, the developer chooses, per valid finding: fix now, defer, or reject. Nothing is changed for a finding without that choice. `[I: Req 4, Human in the loop]`
- **DEV-2 Must.** The developer can stop the loop at any choice point. Stopping goes straight to the final report (REP-1). `[I: Req 8]`
- **DEV-3 Must.** There is no unattended mode in this version. _(Intent open question 2 is left to a later intent.)_ `[I: Human in the loop]`

## Fixes

- **FIX-1 Must.** A fix changes only what its finding needs; no unrelated refactoring. _(Derived: unrelated changes would themselves be reviewed in the next round.)_
- **FIX-2 Must.** Each fix comes with a test that fails without the fix, where a test is possible. The command shows that the test fails with the fix removed and passes with it in place. `[I: Req 5]`
- **FIX-3 Must.** Showing a test fail without its fix must leave every file exactly as it was afterwards, including other uncommitted changes, and the command checks that it did. _(Derived: in the demo, undoing such a check with `git checkout` threw away uncommitted fixes.)_
- **FIX-4 Must.** Where no test is possible (for example a comment, a document, or infrastructure code without a test harness), the round says so for that fix. `[I: Req 5]`
- **FIX-5 Must.** The command never commits, pushes, changes branches or rewrites history. It writes nothing outside the repo except its own temp directory. `[I: Writes to the repo]`

## Tests

- **TST-1 Must.** After each round's fixes, the command runs the project's tests. The developer confirms the test command in the first round; the command may suggest one from the repo. `[I: Req 6]`
- **TST-2 Must.** A failing test run stops the loop and reports which tests failed, before the next review. `[I: Req 6]`

## Memory and stopping

- **MEM-1 Must.** A finding the developer rejected or deferred is not proposed again in a later round of the same run, even when reworded, as long as it concerns the same file and the same issue. `[I: Req 7]`
- **MEM-2 Must.** What the loop remembers lives only in the run's temp directory; nothing is written to the repo for it. `[I: Memory between rounds]`
- **STOP-1 Must.** The loop stops when a round has no new finding judged valid at high or medium severity, when the round limit is reached, or when the developer stops it (DEV-2), whichever comes first. `[I: Req 8]`
- **STOP-2 Must.** Each round shows the panel score, but the score never decides whether the loop continues. `[I: Req 9]`

## Report

- **REP-1 Must.** At the end the command prints: the last review exactly as `finish` printed it; per round, what was fixed and with which test; a **Known follow-ups** section listing deferred findings with their reasons, ready to paste into a PR description; and the rejected findings with their reasons. `[I: Req 10]`
- **REP-2 Should.** For findings rejected as standing design decisions, the report suggests `extra_focus` lines for the repo config, so later reviews stop raising them. `[I: Memory between rounds]`
- **REP-3 Must.** Nothing is posted to GitHub. `[I: Req 11]`

## Out of scope

- CI behaviour (unchanged).
- An unattended mode (DEV-3).
- Committing, pushing or opening the PR (FIX-5).
