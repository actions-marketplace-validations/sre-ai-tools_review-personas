# Design: personas as an array input

> Status: **Approved** by the owner, 2026-10-15.
>
> Implements [requirements.md](requirements.md) (approved 2026-10-15). Requirement IDs appear in brackets, e.g. [INP-3]. Decisions are numbered P1, P2, … so they don't clash with 0001's D1–D13 or 0002's T1–T9.

## Decisions

| # | Topic | Status |
|---|---|---|
| P1 | One parser for both forms | ✅ Decided |
| P2 | Parsing rules | ✅ Decided |
| P3 | Errors | ✅ Decided |
| P4 | Workflow, action and model input | ✅ Decided |
| P5 | Docs and release | ✅ Decided |
| P6 | Tests | ✅ Decided |

---

## P1. One parser for both forms

**Decision.** Replace `cli._split` with **`config.parse_persona_ids(value: str) -> list[str] | None`**. Both `cmd_ci` and `cmd_prepare` call it where they call `_split` today [INP-11].

**Why `config.py`:**
- `ConfigError` is defined there, and it's the error the parser raises.
- The override it feeds (`personas_override`) is applied in `load_settings`, also there.
- `cli.py` keeps only argument handling.

**Callers need no new error handling.** Both commands already parse the value inside their `try … except ConfigError` block:
- `cmd_ci` maps it to exit code 2;
- `cmd_prepare` does the same.

`local.prepare` and `load_settings` keep their signatures. They still receive `list[str] | None`.

## P2. Parsing rules

`parse_persona_ids` does the following, in order:

1. **Empty:** if `value.strip()` is empty, return `None`, which means every enabled persona [INP-6].
2. **JSON form:** if `value.lstrip()` starts with `[`, read it with `json.loads` [INP-1, INP-3]. The result must be a list whose items are all strings that are non-empty after stripping. Otherwise raise (P3) [INP-7].
   - Each item is stripped [INP-4].
   - `[]` returns `None` [INP-6].
3. **Comma form:** anything else is split on `,`, items are stripped, and empty items are dropped. This is exactly today's `_split`, so existing values behave the same [INP-2, INP-4].
4. **Order and duplicates:** order is kept and duplicates aren't removed, as today [INP-5].

Unknown and disabled ids are still rejected by `load_settings`, after parsing, with its existing message [INP-9].

**Edge case:** a value like `dba, [x]` doesn't start with `[`, so it's read as the comma form. It then fails as an unknown id, which is the same as today.

## P3. Errors

Invalid JSON-form values raise `ConfigError` [INP-7, INP-8] with this message:

```
`personas` must be a JSON array of persona ids like ["aws-architect", "dba"], or comma-separated ids like aws-architect,dba; got '["dba"'
```

- The received value is shown with `repr()`, cut to 200 characters.
- The message shows both accepted forms.
- In CI it appears as `::error::review-personas config error: …` and exits with code 2 (0001 D10).
- Locally, `prepare` prints `review-personas: …` and exits with code 2.

## P4. Workflow, action and model input

**No input is added, removed or renamed** [INP-13]:
- `review.yml` and `action.yml` keep `personas` and `model` as strings.
- `action.yml` already passes both inputs through `env`, never through the script text, so a JSON value with quotes and brackets can't inject shell.

**The only edits** are the `description` text of `personas` in both files, which becomes: *"Persona ids to run, overriding the config: a JSON array like ["aws-architect", "dba"], or comma-separated"* [INP-14].

**Unchanged:**
- The `uses: sre-ai-tools/review-personas@…` line that `release.yml` rewrites (0001 D11).
- `model`, in either file or in `load_settings`. It keeps applying `model_override` to every selected persona [INP-10].

## P5. Docs and release

| File | Change | Req |
|---|---|---|
| `README.md` input table | The `personas` row reads: *JSON array like `'["aws-architect", "dba"]'`, or comma-separated ids; for this run only* | INP-14 |
| `README.md` local section | Add an array example next to the comma example: `/prpanel:review --personas '["dba", "app-developer"]'`, noting the single quotes | INP-12 |
| `examples/caller-workflow.yml` | Add commented-out `personas: '["aws-architect", "dba"]'` and `model:` lines under `with:`, with a note that the comma form also works | INP-14 |
| `commands/review.md` | Argument hint becomes `[--base <branch>] [--personas id,id \| '["id","id"]']` | INP-12 |
| `cli.py` `--personas` help, for both `ci` and `prepare` | *"JSON array or comma-separated ids to run (overrides config)"* | INP-14 |
| `docs/specs/README.md` | Status row for 0003 | — |

**Release.** This change ships in the next **minor** release, because only the accepted values widen [INP-13]. It touches nothing in `prompt.py` or the persona files, so the evals workflow isn't triggered.

## P6. Tests

All tests are unit tests with no network.

**In `tests/test_config.py`**, cases for `parse_persona_ids`:

| Input | Expected | Req |
|---|---|---|
| `'["aws-architect", "dba"]'` | `["aws-architect", "dba"]` | INP-1 |
| `'  [" dba ", "aws-architect"]'` | `["dba", "aws-architect"]` (trimmed, order kept) | INP-3, INP-4, INP-5 |
| `"aws-architect, dba"`, `"dba,"` | `["aws-architect", "dba"]`, `["dba"]` | INP-2, INP-4 |
| `""`, `"   "`, `"[]"` | `None` | INP-6 |
| `'["dba"'`, `'[{"dba": 1}]'`, `'["dba", 3]'`, `'[""]'`, `'[" "]'` | `ConfigError` whose message contains the value and both forms | INP-7, INP-8 |
| `'{"dba": 1}'` | Read as one comma-form id, so `load_settings` rejects it as unknown | INP-3, INP-9 |

**Through the CLI**, next to the existing `cmd_ci` and `prepare` tests in `tests/test_runner.py` and `tests/test_local.py`:
- `cmd_ci` with `--personas '["dba"]'` reviews only the DBA persona.
- `cmd_ci` with `--personas '["dba"'` returns exit code 2 [INP-7].
- `cmd_ci` with `--personas '["nope"]'` returns exit code 2 with the existing unknown-id message [INP-9].
- `prepare` with `--personas '["dba"]'` writes one prompt file [INP-11].

**Comments.** Test names or comments cite the INP IDs, as the 0001 tests do.

_Corrected 2026-10-15 during the build: the `'{"dba": 1}'` case moved to its own row to match INP-3 (see INP-7's note)._
