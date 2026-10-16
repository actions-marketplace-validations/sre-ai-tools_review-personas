# Intent: security persona with vulnerability scanners

> Status: **Approved** by the owner, 2026-10-15.

## What

A fifth built-in persona, **Security engineer**, backed by four open-source scanners:

| Scanner | Finds |
|---|---|
| **Semgrep** | Insecure code patterns (SAST): injection, unsafe deserialisation, weak crypto |
| **Trivy** | Known vulnerabilities (CVEs) in dependencies and lockfiles, and in container images defined in the repo |
| **Gitleaks** | Secrets committed in the change |
| **Checkov** | Misconfigured infrastructure as code: Terraform, CloudFormation, Kubernetes, Dockerfiles |

The scanners run on the PR. Their results go to the security persona as evidence. The persona then reviews the PR like the others:
- it decides which issues matter;
- it gives a score and at most 3 findings;
- it says **not relevant** when the PR touches nothing security-related and the scanners found nothing.

## Why

**The panel has no security reviewer, and an LLM alone is a weak one.** Models miss known CVEs and secrets, and they invent vulnerabilities. Scanners are good at those things, but they're noisy, and their raw output is too long for a reviewer to read on every PR. Combining the two gives human reviewers a short, prioritised security pre-review, in line with 0001's goal of faster human review. The persona can also catch what scanners can't, such as missing authorisation on a new endpoint.

## Who uses it

- Caller repos, through the reusable workflow, the same as the other personas.
- Developers locally, through `/prpanel:review`.

## Requirements

1. A built-in security persona that reviews the PR like the other personas: score, up to 3 findings, or not relevant. It counts toward the cumulative score.
2. In CI, Semgrep, Trivy, Gitleaks and Checkov run on the PR, and their findings are given to the security persona as input, and to no other persona.
3. Scanners report only what the PR introduces or changes. Issues already in the base branch are left out, so each PR's review is about that PR.
4. **No secret value ever reaches a model or the PR comment.** Gitleaks findings are passed on as file, line and rule only. This keeps 0001's sensitive-file guarantee (DAT-1).
5. If a scanner fails or times out, the persona still reviews with what it has, and the comment says which scanner didn't run. One failing scanner never fails the run (0001 D10).
6. The comment shows which scanners ran and how many raw findings each one reported, so a human can go to the full scanner output.
7. Scanner versions are pinned, so a run is reproducible and a new scanner release can't change results unannounced.
8. The run still meets 0001's 5-minute target (CI-4) on a typical PR.
9. Callers can turn off the persona, or any single scanner, through config.

## Decisions

_Confirmed by the owner, 2026-10-15._

| Decision | Choice |
|---|---|
| Scanners and persona | **The scanners feed the persona; they don't post their own section.** The comment stays one short panel review (COM-1). A one-line scanner summary per requirement 6 is the only addition. |
| Where scanner findings go | **Only to `appsec`. All security findings stay together under the security persona.** No scanner output goes to other personas, including Checkov's Terraform findings, so a security issue is reported in one place. The other personas' focus is unchanged. |
| Persona id | **`appsec`, not `security`.** Callers who copied `examples/security.md` already have a custom `security` persona, and a built-in with the same id would make their runs fail. That would be a breaking change. |
| On by default | **Yes, for new major version v2.** Adding a persona to everyone's panel changes their comment, score and Bedrock cost, so existing `@v1` callers keep four personas. On v1 it is opt-in. |
| Scan scope | **Changed files only, compared with the merge base,** with base-branch issues removed. This is the same file set as the other personas, after the sensitive-file filter for model input. Gitleaks also scans sensitive files, because finding secrets is its job; only file, line and rule leave the scanner. |
| Rulesets | **Free, redistributable rules only:** Semgrep's community rules (`p/default`), and Trivy, Gitleaks and Checkov with their built-in rules. No Semgrep login or paid rules. Callers can add their own Semgrep config. |
| Local runs | **The scanners run locally when they are installed, and are skipped with a note when they are not.** The persona still reviews. Installing scanners isn't required to use `/prpanel:review` (LOC-4). |
| Gating | **Advisory only, like every persona.** A critical CVE or a leaked secret doesn't fail the check (SCO-3). Callers who want a gate should run the scanners in their own required workflow. |
| `examples/security.md` | **Kept as the example of a custom persona,** with a note pointing to the built-in `appsec`. |

## Out of scope

- Blocking merges on scanner findings.
- Uploading SARIF to GitHub code scanning, or inline line comments.
- Scanning the whole repo, git history beyond the PR, or running containers and live infrastructure (DAST).
- Paid or login-only rulesets (Semgrep Pro, Snyk, etc.).
- Fixing or auto-remediating findings.

## Success looks like

- On the testbed, seeded issues for each scanner are caught by `appsec`: a vulnerable dependency, a committed fake secret, an injection pattern and an open security group. Clean scenarios get no false alarms from it.
- No secret value from a Gitleaks finding appears in a model prompt, reply or PR comment.
- The run still finishes within 5 minutes on the testbed's typical scenario.
- The evals include security cases, and `appsec` meets the same quality bar as the other personas.

## Still open

- **How the scanners are installed in CI:** pinned binaries, `pip` (Semgrep, Checkov) and release downloads (Trivy, Gitleaks), or their official actions. To be decided in design.md, weighing speed, pinning and supply-chain risk.
