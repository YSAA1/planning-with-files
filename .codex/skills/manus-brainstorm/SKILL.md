---
name: manus-brainstorm
description: Codex explicit brainstorming entrypoint. Discuss goals, constraints, and tradeoffs before any planning files are created.
user-invocable: true
allowed-tools: "Read, Bash, Glob, Grep"
metadata:
  version: "2.23.0"
---

# Manus Brainstorm

Use this Codex-specific command to discuss a task before planning-with-files starts.

Rules:
- Do not create `task_plan.md`.
- Do not create `findings.md`.
- Do not create `progress.md`.
- Do not start the planning-with-files workflow yet.
- Stay in discussion mode until the user explicitly chooses `/manus-plan`.

Workflow:
1. Clarify the user's goal, success criteria, audience, scope boundaries, constraints, and tradeoffs.
2. Explore the repository or local environment when that helps reduce ambiguity.
3. Ask targeted follow-up questions only when high-impact ambiguity remains.
4. Recommend a concrete next step.
5. End with a short section titled `Brainstorm Summary` using this structure:

## Brainstorm Summary
- Goal:
- Success criteria:
- In scope:
- Out of scope:
- Constraints:
- Risks:
- Recommended next step:

Do not write any planning files during brainstorming.
