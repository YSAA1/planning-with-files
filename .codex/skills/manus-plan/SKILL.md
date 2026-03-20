---
name: manus-plan
description: Codex soft entrypoint for the planning-with-files workflow. Recommend brainstorming first, then invoke planning-with-files when the user confirms.
user-invocable: true
allowed-tools: "Read, Write, Edit, Bash, Glob, Grep"
metadata:
  version: "2.23.0"
---

# Manus Plan

Use this Codex-specific command as a soft entrypoint into the planning-with-files workflow.

Before invoking the core planning skill:
1. Look for a recent `Brainstorm Summary` in the current conversation.
2. If there is no recent Brainstorm Summary:
   - Explain that `/manus-brainstorm` is recommended before planning.
   - Briefly explain that planning will create `task_plan.md`, `findings.md`, and `progress.md`.
   - ask the user whether to continue.
   - Do not create any planning files until the user confirms.
3. If there is a recent `Brainstorm Summary`, use it to seed the initial goal, success criteria, constraints, and recommended approach.

Then:
- Invoke the `planning-with-files` skill.
- follow it exactly as presented.
- Create planning files in the current project directory, not in the skill directory.
- Keep the workflow in the same language the user is already using.
- Do not spawn any subagent during brainstorming or initial planning-file creation.
- After planning files exist and the task has moved into execution, review, or verification work, the main agent may delegate read-heavy tasks to the custom subagents defined in `.codex/agents/research.toml`, `.codex/agents/verification.toml`, and `.codex/agents/review-test.toml`.
- Those subagents are readonly helpers for post-planning execution support only.
- Subagents may not edit code.
- Subagents may not write `task_plan.md`, `findings.md`, or `progress.md`.
- The main agent owns all writes and merges subagent summaries back into the planning files.

If the user decides not to continue yet, stop and recommend `/manus-brainstorm`.
