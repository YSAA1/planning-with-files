---
name: manus-status
description: Codex explicit planning status entrypoint. Show planning-with-files progress without conflicting with built-in status commands.
user-invocable: true
allowed-tools: "Read, Bash, Glob, Grep"
metadata:
  version: "2.23.0"
---

# Manus Status

Read `task_plan.md` from the current project directory and display a compact planning status summary.

## What to Show

1. **Current Phase**: Extract from the `## Current Phase` section.
2. **Phase Progress**: Count phases and their status (`pending`, `in_progress`, `complete`).
3. **Phase List**: Show each phase with a compact status icon.
4. **Errors**: Count entries in the `## Errors Encountered` table if present.
5. **Files Check**: Confirm which planning files exist.

## Status Icons

- `[ ]` or `pending` → ⏸️
- `in_progress` → 🔄
- `[x]` or `complete` → ✅
- `failed` or `blocked` → ❌

## Output Format

```text
📋 Manus Status

Current: Phase {N} of {total} ({percent}%)
Status: {status_icon} {status_text}

  {icon} Phase 1: {name}
  {icon} Phase 2: {name} ← you are here
  {icon} Phase 3: {name}
  ...

Files: task_plan.md {✓|✗} | findings.md {✓|✗} | progress.md {✓|✗}
Errors logged: {count}
```

## If no planning files exist

If no planning files exist, say so explicitly and suggest `/manus-brainstorm` for discovery or `/manus-plan` to start planning.

Keep it brief.
