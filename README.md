# review-personas

A panel of AI reviewers for GitHub pull requests: **AWS architect**, **App developer**, **UI developer** and **DBA**, plus any personas you add. Each persona reviews the PR from its own angle and either scores it from 0 to 10 with up to 3 short findings, or says it is **not relevant**. The results appear in one PR comment with an advisory cumulative score, so human reviewers start from a specialist pre-review.

- **CI:** runs on AWS Bedrock and posts the comment on every push, editing it in place.
- **Locally:** `/prpanel:review` in Claude Code reviews your branch before you open the PR, with the same personas, rules and config.
- **Advisory:** the score never blocks a merge.

```markdown
## 🧩 Persona review: 7.3/10 (advisory)

| Persona | Score | Summary |
|---|---|---|
| ☁️ AWS architect | 8 | IAM scoped well; add retries. |
| 🧑‍💻 App developer | 7 | Null user not handled. |
| 🎨 UI developer | – | Not relevant |
| 🗄️ DBA | 7 | Migration locks users table. |

**🗄️ DBA**
- 🔴 `db/001.sql:3` Create the index CONCURRENTLY.
```

How this was specified and why: [docs/specs/0001-persona-review](docs/specs/0001-persona-review/).

## Quick start

**On your machine, before opening a PR** (needs [Claude Code](https://claude.com/claude-code) and [uv](https://docs.astral.sh/uv/)):

- Install once, in Claude Code:
  - `/plugin marketplace add sre-ai-tools/review-personas`
  - `/plugin install prpanel@review-personas`
- On your branch, run one of:
  - `/prpanel:review`: shows the panel's review. Changes nothing.
  - `/prpanel:review-loop`: reviews, checks each finding, asks which to fix, fixes them with a test each, and reviews again. Never commits.
- No AWS account needed: it uses your Claude Code login.

**On every PR, in GitHub Actions** (needs an AWS account with Bedrock):

- Create an IAM role GitHub can assume for your repo's PRs, allowed only to call one Bedrock model ([details](#1-aws-an-iam-role-github-can-assume)).
- Enable that model in the Bedrock console.
- Copy [examples/caller-workflow.yml](examples/caller-workflow.yml) to `.github/workflows/review-personas.yml` and set the role ARN.
- Open a PR: one comment appears with a score out of 10. Higher is better; it never blocks a merge.

**Optional:**

- Tune personas in `.github/review-personas.yml` ([example](examples/review-personas.yml)).
- Add your own reviewer: one Markdown file in `.github/review-personas/personas/` ([example](examples/security.md)).

The rest of this README is the full reference.

## Use it in CI

### 1. AWS: an IAM role GitHub can assume

Create an IAM role with a trust policy for GitHub's OIDC provider (`token.actions.githubusercontent.com`) that is scoped to your repo:

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::<ACCOUNT>:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
    "StringLike": { "token.actions.githubusercontent.com:sub": "repo:<ORG>/<REPO>:pull_request" }
  }
}
```

Use a **dedicated role** for this workflow, with no permissions beyond the one below. Consider a CloudWatch alarm on Bedrock invocations or spend.

Give it permission to call the model. The default is `qwen.qwen3-32b-v1:0` (Qwen3 32B), called on demand in the workflow's region:

```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": [
    "arn:aws:bedrock:*::foundation-model/qwen.qwen3-32b-v1:0"
  ]
}
```

Enable the model in the Bedrock console for your account, in the region you pass as `aws-region`. To use a model that runs through an inference profile instead (for example `global.anthropic.claude-opus-5-5`), allow both the profile (`arn:aws:bedrock:*:<ACCOUNT>:inference-profile/<id>`) and its underlying foundation model. To find model IDs, run `aws bedrock list-foundation-models` and `aws bedrock list-inference-profiles`.

### 2. Add the workflow

Copy [examples/caller-workflow.yml](examples/caller-workflow.yml) to `.github/workflows/review-personas.yml` and set `aws-role-arn`.

| Input | Default | |
|---|---|---|
| `aws-role-arn` | required | Role from step 1 |
| `aws-region` | `us-east-1` | Region for Bedrock calls |
| `config-path` | `.github/review-personas.yml` | Optional config file |
| `personas` | all enabled | JSON array like `'["aws-architect", "dba"]'`, or comma-separated ids; for this run only |
| `model` | from config | Model ID for every persona |

Pin `@v1` to get compatible updates automatically, or `@v1.2.3` to freeze a version.

**Important:**
- **Don't make the check required.** It fails only when the pipeline itself is broken, for example when AWS auth fails for every persona or the comment can't be posted. It never fails on a low score.
- **Use `pull_request`, never `pull_request_target`.** PR content is untrusted. PRs from forks get no OIDC token, so they are not reviewed.

### 3. Optional: configure

- **Config file:** copy [examples/review-personas.yml](examples/review-personas.yml) to `.github/review-personas.yml`. It lets you disable personas, change models, add extra focus, set path filters, extend the sensitive-file deny list, and add prices for a cost estimate. Unknown keys fail the run with a message saying what's wrong.
- **Custom personas:** add Markdown files to `.github/review-personas/personas/`, like [examples/security.md](examples/security.md). The file name is the persona id. Custom personas run automatically.
- **Files never sent to a model:** `.env*`, private keys and certificates, `*.tfstate`, `.npmrc`, `.pypirc`, `*credentials*.json`, `*secret*.y*ml`, plus your `exclude_sensitive` patterns. They are listed in the comment as *not reviewed: sensitive*.

The job summary shows tokens per persona. With `prices` set, it also shows estimated cost.

## Use it locally (Claude Code)

You need [uv](https://docs.astral.sh/uv/) installed (`brew install uv`). Then, in Claude Code:

```
/plugin marketplace add sre-ai-tools/review-personas
/plugin install prpanel@review-personas
```

Then, on your feature branch:

```
/prpanel:review                       # branch vs the remote's default branch, incl. uncommitted work
/prpanel:review --base develop
/prpanel:review --personas dba,app-developer
/prpanel:review --personas '["dba", "app-developer"]'   # keep the single quotes
```

- **Model and config:** it uses your Claude Code model and the repo's `.github/review-personas.yml`. Model settings in the config are ignored locally.
- **Output:** the result is shown in the chat only. Nothing is posted to GitHub, and nothing is written inside the repo.

### Review, fix and review again

```
/prpanel:review-loop                  # up to 2 rounds
/prpanel:review-loop 3 --personas dba,app-developer
```

Each round reviews the branch as `/prpanel:review` does, checks every finding against the code, and asks you which to fix. Each fix comes with a test that is shown to fail without it. The loop stops when a round finds nothing new at high or medium severity, at the round limit, or when you stop it. It ends with the last review and a **Known follow-ups** list to paste into the PR description.

- **It edits code and tests in the repo,** unlike `/prpanel:review`. It never commits, pushes or switches branches.
- **You choose every fix.** Findings it judges false are listed with a reason, not fixed. The score is shown but never decides anything.

How it was specified: [docs/specs/0005-review-loop](docs/specs/0005-review-loop/).

## Measure the pilot

```sh
GITHUB_TOKEN=... uvx --from git+https://github.com/sre-ai-tools/review-personas review-personas \
  metrics --repo <org>/<repo> --adopted 2026-11-01 --weeks 4
```

It prints the median time to first human review and the median time to merge, for the weeks before and after the adoption date.

## Develop

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]"
.venv/bin/pytest                                   # unit tests; no network
.venv/bin/pytest tests/test_reply.py -k limits     # one test
.venv/bin/ruff check . && .venv/bin/ruff format .
.venv/bin/review-personas ci --base-ref main --dry-run   # real Bedrock call, prints the comment
.venv/bin/python evals/run.py                      # eval suite, real Bedrock calls
```

### Releasing

Run the **Release** workflow with a version such as `1.2.3`. It runs the tests and evals, pins the reusable workflow's action reference and the package and plugin versions, then tags `v1.2.3` and moves `v1`.

Breaking changes to workflow inputs or the config format need a new major version.

### Evals setup

The evals run code from the PR, with AWS credentials, so they are gated:

1. **Create the environment.** In this repo's settings, create an Environment named `evals`. Add yourself as a **required reviewer**, and set the variables `EVALS_AWS_ROLE_ARN` and, optionally, `EVALS_AWS_REGION`.
2. **Create the role.** Make an IAM role whose trust policy accepts only that environment: `"token.actions.githubusercontent.com:sub": "repo:sre-ai-tools/review-personas:environment:evals"`. Its only permission is `bedrock:InvokeModel` on the eval models (see the policy above).
3. **Approve each run.** A PR that changes personas, the prompt or evals waits for your approval before the evals run. Read the diff before you approve, especially changes to `evals/`.
