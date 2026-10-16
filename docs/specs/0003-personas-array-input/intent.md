# Intent: personas as an array input

> Status: **Approved** by the owner, 2026-10-15.

## What

Callers of the reusable workflow choose which personas run by passing a list, written the way a list is normally written in YAML or JSON:

```yaml
uses: sre-ai-tools/review-personas/.github/workflows/review.yml@v1
with:
  aws-role-arn: arn:aws:iam::123456789012:role/github-review-personas
  personas: '["aws-architect", "dba"]'
  model: global.anthropic.claude-opus-5-5
```

`model` keeps its current behaviour: one Bedrock model ID for every persona that runs.

## Why

**The tool is reused across repos, so each caller should be able to pick its panel and model from the workflow file alone.** Both inputs already exist (0001, CI-1), but `personas` accepts only a comma-separated string (`aws-architect,dba`). A list is what callers expect to write, and it matches how persona lists already appear in the config file.

## Who uses it

Repos that call `review.yml` or the composite action directly.

## Requirements

1. The `personas` input accepts a JSON array of persona ids, for example `'["aws-architect", "dba"]'`.
2. The current comma-separated form keeps working, so existing callers don't break (CI-6).
3. An empty value (`""` or `[]`) runs every enabled persona, as it does today.
4. A malformed array, or an array whose items aren't non-empty strings, fails the run as a config error (exit code 2, D10), with a message showing the expected format.
5. Unknown or disabled ids still fail as they do today.
6. `model` is unchanged: one model ID for all personas, overriding the config.
7. The README input table and the caller example show the array form.

## Decisions

_Confirmed by the owner, 2026-10-15._

| Decision | Choice |
|---|---|
| Input type | **A string holding a JSON array.** GitHub `workflow_call` and action inputs can only be strings, booleans or numbers, so a real YAML list can't be passed. |
| Comma-separated form | **Kept as an accepted alternative.** Dropping it would be a breaking change to a public input and need a new major version. |
| How the form is detected | **A value starting with `[` is parsed as JSON.** Anything else is split on commas, as today. |
| Local runs | **`review-personas prepare --personas` accepts the same two forms**, using the same parser, so CI and local don't drift (D1). |
| Per-persona models | **Not added.** One model for all personas through the input. Per-persona models stay in the config file (`personas.<id>.model`). |

## Out of scope

- A per-persona model input.
- Any change to config file keys or persona frontmatter.
- Changing which personas are enabled by default.

## Success looks like

- A caller using `personas: '["aws-architect", "dba"]'` gets a comment with exactly those two personas.
- Existing callers using `aws-architect,dba` see no change.
- A typo like `'["dba"'` fails the run with a message that says what's wrong.
