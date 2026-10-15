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

Give it permission to call the model. The default is the `global.anthropic.claude-opus-5-5` inference profile, which needs both the profile and the underlying model:

```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": [
    "arn:aws:bedrock:*:<ACCOUNT>:inference-profile/global.anthropic.claude-opus-5-5",
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-opus-5-5"
  ]
}
```

Enable the model in the Bedrock console for your account. To find other model IDs, run `aws bedrock list-inference-profiles`.

### 2. Add the workflow

Copy [examples/caller-workflow.yml](examples/caller-workflow.yml) to `.github/workflows/review-personas.yml` and set `aws-role-arn`.

| Input | Default | |
|---|---|---|
| `aws-role-arn` | required | Role from step 1 |
| `aws-region` | `us-east-1` | Region for Bedrock calls |
| `config-path` | `.github/review-personas.yml` | Optional config file |
| `personas` | all enabled | Comma-separated ids, for this run only |
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
```

- **Model and config:** it uses your Claude Code model and the repo's `.github/review-personas.yml`. Model settings in the config are ignored locally.
- **Output:** the result is shown in the chat only. Nothing is posted to GitHub, and nothing is written inside the repo.

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

The evals need repository variables `EVALS_AWS_ROLE_ARN` (and optionally `EVALS_AWS_REGION`), pointing at a role trusted for this repo with Bedrock access.
