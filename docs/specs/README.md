# Specs

This project follows the [AI-native SDLC playbook](https://academy.claude.com/courses/ai-native-sdlc-playbook). Each change gets a numbered folder, written in this order. Each file must be approved by the owner before the next one starts:

1. `intent.md`: what, why, and the decisions (Plan)
2. `requirements.md`: testable requirements traced to the intent (Design)
3. `design.md`: how the requirements are met (Design)

Code is written only after `design.md` is approved. A later change, such as a metric drifting in production or a new need, starts a new folder with the next number and its own `intent.md`.

| # | Change | Status |
|---|---|---|
| [0001](0001-persona-review/) | Persona PR review pipeline and local Claude Code runs | Built on `feat/0001-persona-review`; awaiting Bedrock and end-to-end verification |
| [0002](0002-test-applications/) | Test applications for end-to-end verification of 0001 | Testbed live at [sre-ai-tools/review-personas-testbed](https://github.com/sre-ai-tools/review-personas-testbed) with its IAM role; awaiting the first verification run |
| [0003](0003-personas-array-input/) | `personas` workflow input accepts a JSON array | Merged to `main`; testbed pinned to `4331a71`; not yet released |
| [0004](0004-security-persona/) | Security persona backed by Semgrep, Trivy, Gitleaks and Checkov | Requirements approved; design drafted, awaiting approval (S5 open) |
| [0005](0005-review-loop/) | `/prpanel:review-loop`: review, verify, fix and re-review locally | Requirements approved; design drafted, awaiting approval |
