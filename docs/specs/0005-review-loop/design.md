# Design: review loop

> Status: **Approved** by the owner, 2026-10-24, including the proposed details at the end. Implements [requirements.md](requirements.md) (approved 2026-10-24). Requirement IDs appear in brackets, e.g. [FIX-3].

## Decisions

| # | Topic | Status |
|---|---|---|
| D1 | Files and shape of the command | ✅ Decided |
| D2 | Findings as data: `finish --json` | ✅ Decided |
| D3 | Verification: a read-only verifier subagent | ✅ Decided |
| D4 | The developer's choice | ✅ Decided |
| D5 | Proof that a test fails without its fix: `review-personas loop` | ✅ Decided |
| D6 | Tests, memory and stopping | ✅ Decided |
| D7 | The final report | ✅ Decided |
| D8 | Testing and release | ✅ Decided |

---

## D1. Files and shape of the command

**Decision.** Two new plugin files, two additive CLI changes, no change to the review itself.

| File | What |
|---|---|
| `commands/review-loop.md` | The `/prpanel:review-loop` command: the loop, in prompt form, like `commands/review.md` [LOOP-3] |
| `agents/finding-verifier.md` | Read-only subagent that gives each finding a verdict (D3) |
| `src/review_personas/local.py`, `cli.py` | `finish --json` (D2) |
| `src/review_personas/loop.py`, `cli.py` | `review-personas loop save | check` (D5) |

One round:

```
 prepare ──▶ persona-reviewer × N ──▶ finish --json            (same as /prpanel:review) [LOOP-2]
                                         │ findings + review Markdown
                                         ▼
                        finding-verifier × N (read-only) ──▶ verdicts      [VER-1, VER-3]
                                         ▼
                 merge duplicates, drop already-decided ──▶ ask developer  [VER-2, MEM-1, DEV-1]
                                         ▼
          loop save ──▶ fix + test ──▶ loop check (fails without fix?) ──▶ project tests [FIX-2, FIX-3, TST-1]
                                         ▼
                                  stop? ──no──▶ next round                  [STOP-1]
```

**Why.** As 0001 D1 says, code enforces rules and prompts do the judging. The two places where a slip would cost the developer work, structured findings and restoring files, are code. Verification, matching reworded findings and fixing are judgment, so they stay in the session.

**Arguments [LOOP-1].** The command parses its first argument as `rounds` when it is a whole number; it must be 1 to 5, default 2, otherwise the command stops before reviewing. Everything else is passed to `prepare` unchanged, as `/prpanel:review` does.

## D2. Findings as data: `finish --json`

**Decision.** `review-personas finish <dir> --json` prints, instead of Markdown:

```json
{
  "review": "<the same Markdown finish prints today>",
  "score": 7.3,
  "personas": [
    {"id": "dba", "relevant": true, "score": 7, "summary": "…",
     "findings": [{"severity": "high", "file": "db/001.sql", "line": 3, "comment": "…"}]}
  ]
}
```

- Findings are the validated ones, after `reply.parse_reply` enforces the limits (0001 REV-4); the loop never reads raw replies.
- Retry behaviour (exit code 3) and the deleted working directory (0001 LOC-5) are unchanged.
- Without `--json`, output is byte-for-byte as today.

**Why.** The loop needs findings it can verify and remember. Parsing the rendered Markdown would break whenever the comment layout changes, and the Markdown escapes model text (`render.escape`).

**Line numbers are hints.** In the acme-app demo, findings sometimes cited lines past the end of the file. The verifier locates the issue by file and content, never by line alone. Fixing the line numbers is a separate change.

## D3. Verification: a read-only verifier subagent

**Decision.** For each persona with findings, the command starts one `finding-verifier` subagent, in parallel, with tools **Read, Grep and Glob only**. It receives the findings and the list of already-decided issues (D6), and returns one JSON verdict per finding:

```json
{"finding": 1, "verdict": "valid" | "false" | "defer", "reason": "<one line citing file:line it checked>",
 "issue": "<the issue in ten words or fewer>", "already_decided": null | <decision index>}
```

- **Untrusted content [VER-3].** The agent's instructions say that file contents and finding text are data: instructions inside them never change the verdict. It has no tool that can write, run commands or reach the network, so an injected instruction has nothing to act with.
- **Duplicates [VER-2].** The session merges findings whose verdicts name the same file and the same `issue`, keeping every persona's name.
- **Session vs subagent.** Verifying in the session would fill its context with every file a verifier reads, and lose 0001's split between reviewers and the session.

## D4. The developer's choice

**Decision.** After verification, the session shows a compact table of valid and deferrable findings (severity, file, issue, verdict reason, personas) and false ones with their reasons. It then asks with Claude Code's multiple-choice question tool, up to four findings per question set:

| Option | Means |
|---|---|
| Fix now | Fixed this round [DEV-1] |
| Defer | Goes to Known follow-ups (D7) and memory |
| Reject | Goes to memory with the verifier's reason |
| Stop the loop | Ends at this point and prints the report [DEV-2] |

Findings judged **false** are not asked about; they go to memory as rejected, and the developer can override in the free-text answer. There is no unattended mode [DEV-3].

## D5. Proof that a test fails without its fix: `review-personas loop`

**Decision.** Two small subcommands in a new `loop.py`, so file handling is code, not prompt [FIX-3]:

- `review-personas loop save <state-dir> <file>…`: before the session edits any file for a fix, copies each file's current content into the loop's state directory with its SHA-256.
- `review-personas loop check <state-dir> --test "<command>"`:
  1. records the SHA-256 of each saved file **as fixed now**;
  2. writes the saved pre-fix content back for code files only (test files keep the new test);
  3. runs the test command and records whether it failed;
  4. writes the fixed content back, and checks every SHA-256 matches step 1;
  5. exits 0 if the test failed without the fix and every file was restored; 4 if the test passed without the fix (it proves nothing); 5 if any file could not be restored, printing which and where its copy is.

`loop check` never runs `git`. Files the fix didn't touch, including other uncommitted work, are never written [FIX-3]. It restores in a `finally` block, so an interrupted test run still puts the fix back.

The session calls `save` before editing and `check` after writing the fix and its test [FIX-2]. Exit 4 means the session rewrites the test; exit 5 stops the loop. A fix with no possible test (a comment, a document, infra without a test harness) skips `check` and says so [FIX-4]. The session edits only files the finding needs and never commits, pushes or switches branches [FIX-1, FIX-5].

## D6. Tests, memory and stopping

- **Project tests [TST-1, TST-2].** In round 1 the session suggests a test command from the repo (`CLAUDE.md`, `pyproject.toml`, `package.json`, `Makefile`) and asks the developer to confirm or edit it. It runs after each round's fixes; a failure stops the loop with the failing tests.
- **State [MEM-2].** `mktemp -d` at the start gives the loop's state directory, outside the repo. It holds `state.json` (rounds, test command, decisions) and D5's saved copies. Nothing is written to the repo for state.
- **Memory [MEM-1].** Each decision is `{round, personas, file, issue, decision, reason}`. Every verifier gets the list and marks a finding `already_decided` when it is the same file and the same issue, however reworded. Those are not asked about again.
- **Stopping [STOP-1, STOP-2].** After a round's verdicts, the loop stops when no finding is new, valid and `high` or `medium`; or when the round limit is reached; or on Stop. The score is printed each round and never consulted.

## D7. The final report [REP-1, REP-2, REP-3]

Printed in the session, nothing posted:

1. The last round's review, exactly as `finish` printed it.
2. **Fixed**, per round: the finding, the files changed, the test that proves it (or why there is none).
3. **Known follow-ups**: deferred findings with their reasons, as a Markdown list to paste into the PR description.
4. **Rejected**: findings and reasons.
5. **Suggested `extra_focus`** (REP-2): for rejected findings that read as standing design decisions (for example, "authorisation by role is out of scope"), one line per persona to add to `.github/review-personas.yml`.

The state directory is deleted at the end unless a `loop check` left a file unrestored (D5 exit 5).

## D8. Testing and release

- **Unit tests (no network):** `finish --json` output and its parity with the Markdown; `loop save` and `loop check` for a passing proof, a test that doesn't fail without its fix, an interrupted test run, an unrestorable file, and an unrelated uncommitted file left untouched.
- **End to end, by hand:** run `/prpanel:review-loop 2` on a testbed branch with planted flaws (0002) and check the report, memory across rounds and that nothing outside the fixed files changed.
- **Evals:** none. `prompt.py` and the persona files are unchanged, so the eval workflow isn't triggered.
- **Version:** additive only (a new command, a new flag, a new subcommand), so **v1.1.0**. No public interface changes (CLAUDE.md "Public interface").

## Proposed details to confirm

- D2: `--json` as a flag on `finish`, rather than a new subcommand.
- D4: four findings per question set, the limit of Claude Code's question tool.
- D5: exit codes 4 and 5 for `loop check`, alongside D10's 0–3.
