# Specs

This project follows the [AI-native SDLC playbook](https://academy.claude.com/courses/ai-native-sdlc-playbook). Each change gets a numbered folder, written in this order. Each file must be approved by the owner before the next one starts:

1. `intent.md`: what, why, and the decisions (Plan)
2. `requirements.md`: testable requirements traced to the intent (Design)
3. `design.md`: how the requirements are met (Design)

Code is written only after `design.md` is approved. A later change, such as a metric drifting in production or a new need, starts a new folder with the next number and its own `intent.md`.

| # | Change | Status |
|---|---|---|
| [0001](0001-persona-review/) | Persona PR review pipeline and local Claude Code runs | Built on `feat/0001-persona-review`; awaiting Bedrock and end-to-end verification |
