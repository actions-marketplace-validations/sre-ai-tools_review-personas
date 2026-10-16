# Requirements: security persona with vulnerability scanners

> Status: **Approved** by the owner, 2026-10-15. Derived from [intent.md](intent.md) (approved 2026-10-15). These describe *what* must hold; *how* belongs in design.md.
>
> Each requirement has an ID for traceability. `[I: …]` points to the part of intent.md it comes from, and `[0001: …]` names the 0001 requirements or decisions it builds on or amends. **Must** means required for this change; **Should** means wanted, but the change can ship without it.

## The persona

- **SEC-1 Must.** A built-in persona with id `appsec`, named *Security engineer*, defined like the other built-ins in `src/review_personas/personas/`. It amends 0001 PER-1 from four built-ins to five. `[I: What; Decisions: persona id]` `[0001: PER-1, PER-2, MNT-1]`
- **SEC-2 Must.** `appsec` follows the same review rules and limits as every persona: a score, a one-sentence summary and at most 3 findings of 25 words or fewer, or **not relevant**. Its score counts toward the cumulative score. `[I: Req 1]` `[0001: REV-1 to REV-4, SCO-1, SCO-2]`
- **SEC-3 Must.** `appsec` is not relevant only when the PR touches nothing security-related **and** no scanner reported a finding. When a scanner reported a finding, `appsec` doesn't say not relevant. It either reports the finding, or scores the PR and says in its summary why the scanner findings don't matter. `[I: What]`
- **SEC-4 Must.** `appsec`'s focus covers what the scanners can't see, for example missing authorisation on a new endpoint, unsafe defaults, and trust boundaries. Scanner findings are evidence, not the whole review. `[I: Why]`
- **SEC-5 Must.** On **v1**, `appsec` is off by default: a caller turns it on with `personas.appsec.enabled: true` in config, or by naming it in the `personas` input. From **v2**, it is on by default and can be turned off the same way. `[I: Decisions: on by default]` `[0001: PER-3, CI-6]`
- **SEC-6 Must.** Callers who already have a custom persona with id `security` keep working unchanged. `[I: Decisions: persona id]` `[0001: CI-6]`
- **SEC-7 Must.** The existing per-persona config keys (`enabled`, `model`, `model_params`, `extra_focus`, `paths`) work for `appsec` as for any built-in. `[I: Req 9]` `[0001: PER-4, PER-5]`

## Scanners

- **SCA-1 Must.** In CI, when `appsec` is enabled, Semgrep, Trivy, Gitleaks and Checkov run on the PR before the persona reviews it. When `appsec` isn't enabled, no scanner runs. `[I: Req 2]`
- **SCA-2 Must.** Scanner findings go to `appsec` only. No other persona's prompt contains scanner output. `[I: Decisions: where scanner findings go]`
- **SCA-3 Must.** Each scanner checks only the files the PR changed, compared with the merge base. A finding is kept only if it is on a line the PR added or changed. Trivy is the exception: it keeps a dependency vulnerability only if the PR added that dependency or changed its version. Findings already present on the base branch are dropped. `[I: Req 3; Decisions: scan scope]` `[0001: D4]`
- **SCA-4 Must.** Each scanner covers at least:

  | Scanner | Must detect |
  |---|---|
  | Semgrep | Injection and unsafe-deserialisation patterns in the languages the default ruleset supports |
  | Trivy | Known CVEs in the dependency manifests and lockfiles it supports |
  | Gitleaks | Secrets matching its built-in rules |
  | Checkov | Misconfigurations in Terraform, CloudFormation, Kubernetes manifests and Dockerfiles |

  `[I: What]`
- **SCA-5 Must.** Only free, redistributable rules are used:
  - Semgrep's community `p/default` ruleset;
  - the built-in rules of Trivy, Gitleaks and Checkov.

  No scanner needs a login, token or paid licence. `[I: Decisions: rulesets]`
- **SCA-6 Should.** A caller can add a Semgrep config file of their own, used in addition to the default ruleset. `[I: Decisions: rulesets]`
- **SCA-7 Must.** A caller can turn off any single scanner in config. Turning off all four leaves `appsec` reviewing without scanner evidence. `[I: Req 9]`
- **SCA-8 Must.** Each scanner's version is pinned in this repo. A scanner's version or rules change only with a review-personas release, never at run time. `[I: Req 7]`
- **SCA-9 Must.** Scanners get no network access beyond what they need to download their pinned rules and vulnerability data. They never send PR content to a third party. _(Derived: DAT-1 forbids sending repo content anywhere but the chosen model.)_ `[0001: DAT-1]`

## Data handling

- **SCA-10 Must.** No secret value reaches a model, a reply or the PR comment. A Gitleaks finding is passed on only as file, line and rule id. Fields from any scanner that could quote a matched secret are removed before anything reaches the persona. `[I: Req 4]` `[0001: DAT-1]`
- **SCA-11 Must.** Gitleaks also scans files on the sensitive-file deny list, because finding secrets is its job. The deny list still applies unchanged to model input: no sensitive file's content is sent to any persona. Semgrep, Trivy and Checkov skip sensitive files. `[I: Decisions: scan scope]` `[0001: DAT-1 to DAT-3]`
- **SCA-12 Must.** Scanner output is untrusted input, because a PR author can control what it quotes. It goes inside the prompt's untrusted-content tags, the same as the diff. `[I: Req 2]` `[0001: REV-5]`
- **SCA-13 Must.** Scanner findings given to `appsec` have a size limit. When findings exceed it, the most severe are kept, and the persona is told how many were left out. `[I: Req 8]` `[0001: DAT-4]`

## Failure and reporting

- **SCA-14 Must.** If a scanner fails, times out or isn't installed, `appsec` still reviews with the evidence it has. The comment names each scanner that didn't run and why, in a few words. A scanner failure alone never changes the exit code. `[I: Req 5]` `[0001: D10, COM-4]`
- **SCA-15 Must.** The comment has one line for `appsec` giving, for each scanner, whether it ran and how many findings it reported in the PR's changed lines. The line also links to the workflow run, where the full scanner output is visible in the log. `[I: Req 6]` `[0001: COM-1]`
- **SCA-16 Must.** Scanner results never fail the check, whatever their severity. `[I: Decisions: gating]` `[0001: SCO-3, D10]`

## Performance

- **SCA-17 Must.** With `appsec` enabled, a typical pilot PR (≤ 50 changed files) still gets its comment within 5 minutes of the run starting. Each scanner has its own timeout, so a slow scanner can't push the run past it. `[I: Req 8]` `[0001: CI-4]`
- **SCA-18 Should.** The scanners run in parallel with each other. _(Derived: four scanners one after another would use much of the 5-minute budget.)_

## Local runs

- **LOC-7 Must.** `/prpanel:review` runs each scanner that is installed on the developer's machine, with the same scope (SCA-3), redaction (SCA-10) and untrusted-input handling (SCA-12) as CI. `[I: Decisions: local runs]` `[0001: LOC-3]`
- **LOC-8 Must.** A scanner that isn't installed is skipped with a note naming it and how to install it, and `appsec` still reviews. Installing scanners is never needed to use `/prpanel:review`. `[I: Decisions: local runs]` `[0001: LOC-4]`
- **LOC-9 Must.** Local scanner runs write nothing inside the repo. `[0001: LOC-5]`

## Compatibility, docs and quality

- **SEC-8 Must.** On v1, callers who don't turn on `appsec` see no change: same comment, same score, same run time, and no scanner runs. `[I: Decisions: on by default]` `[0001: CI-6]`
- **SEC-9 Must.** Any new config keys for scanners follow the existing rules: unknown keys fail with a message naming the problem. Adding keys is not a breaking change. `[I: Req 9]` `[0001: PER-7, CI-6]`
- **SEC-10 Must.** The README documents:
  - how to turn on `appsec` and its scanners, and turn single scanners off;
  - what each scanner covers;
  - that results are advisory;
  - that secret values are never sent to a model.

  `examples/security.md` stays as the custom-persona example, with a note pointing to `appsec`. `[I: Decisions: examples/security.md]`
- **SEC-11 Must.** The eval set gains security cases: at least one per scanner, plus one clean PR with no security issue, so `appsec` is checked for false alarms. `[I: Success]` `[0001: MNT-3]`
- **SEC-12 Should.** The testbed (0002) gains scenarios with a vulnerable dependency, a fake secret, an injection pattern and an insecure IaC change. This is done as an amendment to 0002. `[I: Success]`

## Not required (from intent: out of scope)

- Blocking merges on scanner findings.
- SARIF upload to GitHub code scanning, or inline line comments.
- Scanning the whole repo, git history beyond the PR, running containers, or live infrastructure (DAST).
- Paid or login-only rulesets.
- Fixing or auto-remediating findings.
