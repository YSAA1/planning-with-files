# Codex IDE Support

## Overview

planning-with-files works best with Codex as an explicit, slash-friendly workflow in `~/.codex/skills/` or your repository's `.codex/skills/` directory.

For Codex, this repo now ships two layers:
- `planning-with-files` — internal planning workflow skill
- `manus-brainstorm`, `manus-plan`, `manus-status` — explicit user-facing Codex entrypoints

The Codex-facing skills set `allow_implicit_invocation: false` in `agents/openai.yaml`, so Codex does not jump directly into plan-file creation just because a prompt looks complex.

## Installation

Codex auto-discovers skills from `.codex/skills/` directories. Two installation methods:

### Method 1: Workspace Installation (Recommended)

Share the Codex workflow with your entire team by committing the repo's `.codex/` directory:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the Codex integration to your repo
cp -r /tmp/planning-with-files/.codex .

# Commit to share with team
git add .codex/
git commit -m "Add planning-with-files Codex workflow"
git push

# Clean up
rm -rf /tmp/planning-with-files
```

### Method 2: Personal Installation

Install the Codex skills just for yourself:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files
mkdir -p ~/.codex/skills
cp -r /tmp/planning-with-files/.codex/skills/* ~/.codex/skills/
rm -rf /tmp/planning-with-files
```

## Recommended Codex Workflow

Use the explicit Codex commands in this order:

1. `/manus-brainstorm` — discuss the task before any planning files are created
2. `/manus-plan` — enter the planning-with-files workflow after brainstorming or after explicit confirmation
3. `/manus-status` — inspect the current plan-file state

Why these names?
- Codex already has built-in `/plan`, `/plan-mode`, and `/status` commands.
- The `manus-*` names avoid collisions with native Codex commands in both CLI and app surfaces.

## Behavior Notes

- `manus-brainstorm` does not create `task_plan.md`, `findings.md`, or `progress.md`.
- `manus-plan` uses a soft gate: if there is no recent `Brainstorm Summary`, it recommends `/manus-brainstorm` first and asks whether to continue before creating planning files.
- `manus-plan` is a thin wrapper around the internal `planning-with-files` skill, similar to the soft command style used by Claude command entrypoints.
- `planning-with-files` remains available as the internal planning skill, but it is no longer the recommended direct Codex entrypoint.

## Explicit Invocation

If you prefer explicit skill invocation instead of slash commands:

- `$manus-brainstorm`
- `$manus-plan`
- `$manus-status`

Enabled skills also appear in Codex's slash command list, so most users can just type `/` and filter by `manus`.

## Verification

```bash
ls -la ~/.codex/skills/manus-brainstorm/SKILL.md
ls -la ~/.codex/skills/manus-plan/SKILL.md
ls -la ~/.codex/skills/manus-status/SKILL.md
```

## Learn More

- [Installation Guide](installation.md)
- [Quick Start](quickstart.md)
- [Workflow Diagram](workflow.md)
