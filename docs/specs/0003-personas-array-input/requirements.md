# Requirements: personas as an array input

> Status: **Approved** by the owner, 2026-10-15. Derived from [intent.md](intent.md) (approved 2026-10-15). These describe *what* must hold; *how* belongs in design.md.
>
> Each requirement has an ID for traceability. `[I: …]` points to the part of intent.md it comes from, and `[0001: …]` names the 0001 requirements or decisions it builds on. **Must** means required for this change; **Should** means wanted, but the change can ship without it.

## Accepted forms

- **INP-1 Must.** The `personas` input of `review.yml` and of the composite action accepts a JSON array of persona ids, for example `'["aws-architect", "dba"]'`. `[I: Req 1; Decisions: input type]` `[0001: CI-1, PER-3]`
- **INP-2 Must.** The comma-separated form (`aws-architect,dba`) keeps working with the same result as before this change. `[I: Req 2; Decisions: comma-separated form]` `[0001: CI-6]`
- **INP-3 Must.** A value whose first non-whitespace character is `[` is read as a JSON array. Any other value is read as the comma-separated form. `[I: Decisions: how the form is detected]`
- **INP-4 Must.** In both forms, whitespace around each id is ignored, so `'[" dba "]'` and `aws-architect, dba` select the same personas as their trimmed versions. _(Derived: today's comma form already trims.)_
- **INP-5 Must.** The selected personas run in the order given, in either form. _(Derived: today's comma form already keeps the order, and the comment rows follow it.)_

## Empty and invalid values

- **INP-6 Must.** An empty value (`""`, whitespace only, or `[]`) selects every enabled persona, as an empty value does today. `[I: Req 3]` `[0001: PER-3]`
- **INP-7 Must.** A value read as JSON that isn't a valid JSON array, or whose items aren't all non-empty strings (for example `'["dba"'`, `'[{"dba": 1}]'`, `'["dba", 3]'`, `'[""]'`), fails the run as a config error, with exit code 2. `[I: Req 4]` `[0001: D10, PER-7]` _(Corrected 2026-10-15: the example `'{"dba": 1}'` was replaced. It doesn't start with `[`, so under INP-3 it's read as one comma-form id and fails as unknown, per INP-9.)_
- **INP-8 Must.** The error message for INP-7 names the value received and shows both accepted forms. `[I: Req 4; Success: a typo fails with a message]` `[0001: PER-7]`
- **INP-9 Must.** Unknown or disabled ids fail as they do today, in either form. `[I: Req 5]` `[0001: PER-7]`

## Model

- **INP-10 Must.** The `model` input is unchanged: one Bedrock model ID applied to every selected persona, overriding the config. No per-persona model input is added. `[I: Req 6; Decisions: per-persona models]` `[0001: PER-4, CI-3]`

## Local runs

- **INP-11 Must.** `review-personas prepare --personas` accepts both forms with the same rules (INP-3 to INP-9), so a value that works in CI works locally. `[I: Decisions: local runs]` `[0001: D1, LOC-3]`
- **INP-12 Should.** The `/prpanel:review` argument hint and docs show how to pass the array form through the shell, for example `--personas '["dba"]'`. _(Derived: the command passes its arguments to a shell, where an unquoted array would be mangled.)_

## Compatibility and docs

- **INP-13 Must.** No workflow input, action input, config key or persona frontmatter key is added, removed or renamed. Only the accepted values of `personas` widen, so this ships as a minor version. `[I: Out of scope]` `[0001: CI-6]`
- **INP-14 Must.** The README input table and `examples/caller-workflow.yml` show the array form and say that the comma form still works. The workflow and action input descriptions mention both forms. `[I: Req 7]`

## Not required (from intent: out of scope)

- A per-persona model input.
- Any change to config file keys or persona frontmatter.
- Changing which personas are enabled by default.
