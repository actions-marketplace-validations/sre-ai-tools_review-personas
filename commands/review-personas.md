---
description: Review your branch with the review-personas panel (AWS architect, App developer, UI developer, DBA) before opening a PR
argument-hint: "[--base <branch>] [--personas id,id]"
allowed-tools: Bash(command -v uvx), Bash(uvx --from:*), Write, Agent
---

Run a local persona review of the current branch: everything the PR will contain, including uncommitted and untracked work. Nothing is posted to GitHub and nothing is written inside the repository.

Follow these steps exactly. Do not review the code yourself; the persona subagents do the reviewing and the `finish` step produces the final output.

1. **Check for uv.** Run `command -v uvx`. If it prints nothing, stop and tell the user: "review-personas needs uv. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`), then run /review-personas again."

2. **Prepare.** Run:

   ```
   uvx --from "${CLAUDE_PLUGIN_ROOT}" review-personas prepare $ARGUMENTS
   ```

   If it exits non-zero, show its error message to the user and stop. Otherwise it prints JSON with `dir`, `reviewed` and `reviews` (a list of `id`, `prompt_file`, `reply_file`).

3. **Review in parallel.** In a single message, launch one `persona-reviewer` subagent per entry in `reviews`. Give each one only this prompt: `Prompt file: <prompt_file>`. When each subagent finishes, save its final reply **verbatim** to that entry's `reply_file` with the Write tool. Do not edit, fix or reformat the replies. If `reviews` is empty, go straight to step 4.

4. **Finish.** Run:

   ```
   uvx --from "${CLAUDE_PLUGIN_ROOT}" review-personas finish <dir>
   ```

   - **Exit code 3** means some replies were unusable. It prints JSON with a `retry` list of `id`, `prompt_file`, `reply_file` and `message`. Launch one `persona-reviewer` subagent per entry, in a single message, with the prompt `Prompt file: <prompt_file>` followed by a blank line and `<message>`. Save each reply verbatim to its `reply_file`, then run `finish` again. Retry only once: the second `finish` never asks again.
   - **Exit code 0** prints the review as Markdown.

5. **Show the review.** Output the Markdown from `finish` exactly as printed, with nothing added before it. After it, you may offer in one short sentence to help fix the findings.
