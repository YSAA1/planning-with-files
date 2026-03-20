#!/usr/bin/env python3
"""
Session Catchup Script for planning-with-files

Session-agnostic scanning: finds the most recent planning file update across
all relevant previous sessions, then collects all conversation from that point
forward through all subsequent sessions until now.

Supports multiple AI IDEs:
- Claude Code (.claude/projects/)
- Codex (.codex/sessions/YYYY/MM/DD/*.jsonl)
- OpenCode (.local/share/opencode/storage/)

Usage: python3 session-catchup.py [project-path]
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PLANNING_FILES = ["task_plan.md", "progress.md", "findings.md"]
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def normalize_path(project_path: str) -> str:
    """Normalize a project path before comparing IDE-specific storage keys."""
    path = project_path

    # Git Bash / MSYS2: /c/Users/... -> C:/Users/...
    if len(path) >= 3 and path[0] == "/" and path[2] == "/":
        path = path[1].upper() + ":" + path[2:]

    try:
        resolved = str(Path(path).resolve())
        if os.name == "nt" or "\\" in resolved:
            path = resolved
    except (OSError, ValueError):
        pass

    return path


def sanitize_project_path(project_path: str) -> str:
    """Convert a project path to Claude's sanitized storage directory name."""
    sanitized = normalize_path(project_path).replace("\\", "-").replace("/", "-").replace(":", "-")
    sanitized = sanitized.replace("_", "-")
    if sanitized.startswith("-"):
        sanitized = sanitized[1:]
    return sanitized


def detect_ide() -> str:
    """
    Detect which IDE runtime is using this script.
    Returns 'claude-code', 'codex', 'opencode', or 'unknown'.
    """
    script_path = Path(__file__).as_posix().lower()

    if "/.codex/" in script_path:
        return "codex"
    if "/.claude/" in script_path or "/.claude-plugin/" in script_path:
        return "claude-code"
    if os.environ.get("OPENCODE_DATA_DIR"):
        return "opencode"
    if (Path.home() / ".claude").exists():
        return "claude-code"
    if (Path.home() / ".codex" / "sessions").exists():
        return "codex"
    if (Path.home() / ".local" / "share" / "opencode").exists():
        return "opencode"
    return "unknown"


def get_project_dir_claude(project_path: str) -> Path:
    """Convert project path to Claude's storage path format."""
    return Path.home() / ".claude" / "projects" / sanitize_project_path(project_path)


def get_project_dir_opencode(project_path: str) -> Optional[Path]:
    """
    Get OpenCode session storage directory.
    OpenCode uses: ~/.local/share/opencode/storage/session/{projectHash}/

    Note: OpenCode's structure is different - this function returns the storage root.
    Session discovery happens differently in OpenCode.
    """
    data_dir = os.environ.get(
        "OPENCODE_DATA_DIR",
        str(Path.home() / ".local" / "share" / "opencode"),
    )
    storage_dir = Path(data_dir) / "storage"

    if not storage_dir.exists():
        return None

    return storage_dir


def get_sessions_sorted(project_dir: Path) -> List[Path]:
    """Get Claude session files sorted by modification time (newest first)."""
    sessions = list(project_dir.glob("*.jsonl"))
    main_sessions = [session for session in sessions if not session.name.startswith("agent-")]
    return sorted(main_sessions, key=lambda path: path.stat().st_mtime, reverse=True)


def get_sessions_sorted_opencode(storage_dir: Path) -> List[Path]:
    """Get all OpenCode session files sorted by modification time."""
    session_dir = storage_dir / "session"
    if not session_dir.exists():
        return []

    sessions: List[Path] = []
    for project_hash_dir in session_dir.iterdir():
        if project_hash_dir.is_dir():
            sessions.extend(project_hash_dir.glob("*.json"))

    return sorted(sessions, key=lambda path: path.stat().st_mtime, reverse=True)


def get_codex_session_meta(session_file: Path) -> Optional[Dict]:
    """Read the first JSONL record and return it when it is a Codex session meta row."""
    try:
        with open(session_file, "r", encoding="utf-8", errors="replace") as handle:
            first_line = handle.readline()
    except OSError:
        return None

    if not first_line:
        return None

    try:
        record = json.loads(first_line)
    except json.JSONDecodeError:
        return None

    if record.get("type") != "session_meta":
        return None

    return record


def is_codex_primary_session(meta_payload: Dict) -> bool:
    """Return True when the session should count as a primary Codex task session."""
    source = meta_payload.get("source")
    if not isinstance(source, dict):
        return True
    return not source.get("subagent")


def get_sessions_sorted_codex(project_path: str) -> List[Path]:
    """Return Codex session files for the current project, newest first."""
    session_root = Path.home() / ".codex" / "sessions"
    if not session_root.exists():
        return []

    normalized_project = normalize_path(project_path)
    sessions: List[Path] = []

    for session_file in session_root.glob("**/*.jsonl"):
        meta = get_codex_session_meta(session_file)
        if not meta:
            continue

        payload = meta.get("payload", {})
        session_cwd = payload.get("cwd")
        if not session_cwd:
            continue
        if normalize_path(session_cwd) != normalized_project:
            continue
        if not is_codex_primary_session(payload):
            continue
        sessions.append(session_file)

    return sorted(sessions, key=lambda path: path.stat().st_mtime, reverse=True)


def planning_file_from_path(file_path: str) -> Optional[str]:
    """Return the tracked planning filename when the path targets one of them."""
    for planning_file in PLANNING_FILES:
        if file_path.endswith(planning_file):
            return planning_file
    return None


def extract_planning_file_from_patch(patch_text: str) -> Optional[str]:
    """Return the last planning file touched by an apply_patch payload."""
    filename = None
    for raw_path in PATCH_FILE_RE.findall(patch_text):
        matched = planning_file_from_path(raw_path.strip())
        if matched:
            filename = matched
    return filename


def extract_planning_file_from_exec_command(arguments: str) -> Optional[str]:
    """Return a planning filename when an exec_command payload writes one."""
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    command = parsed.get("cmd", "")
    if not isinstance(command, str):
        return None

    patch_match = extract_planning_file_from_patch(command)
    if patch_match:
        return patch_match

    for planning_file in PLANNING_FILES:
        redirection = re.search(
            rf">>?\s*['\"]?[^'\"\n]*{re.escape(planning_file)}['\"]?",
            command,
        )
        tee_write = re.search(
            rf"\btee(?:\s+-a)?\s+['\"]?[^'\"\n]*{re.escape(planning_file)}['\"]?",
            command,
        )
        touch_write = re.search(
            rf"\btouch\s+['\"]?[^'\"\n]*{re.escape(planning_file)}['\"]?",
            command,
        )
        if redirection or tee_write or touch_write:
            return planning_file

    return None


def scan_for_planning_update(session_file: Path) -> Tuple[int, Optional[str]]:
    """
    Quickly scan a session file for planning file updates.
    Returns (line_number, filename) of last update, or (-1, None) if none found.
    """
    last_update_line = -1
    last_update_file = None

    try:
        with open(session_file, "r", encoding="utf-8", errors="replace") as handle:
            for line_num, line in enumerate(handle):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                filename = None
                msg_type = data.get("type")

                if msg_type == "assistant":
                    content = data.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if item.get("type") != "tool_use":
                                continue
                            tool_name = item.get("name", "")
                            if tool_name not in ("Write", "Edit"):
                                continue
                            file_path = item.get("input", {}).get("file_path", "")
                            filename = planning_file_from_path(file_path)
                            if filename:
                                break

                elif msg_type == "response_item":
                    payload = data.get("payload", {})
                    payload_type = payload.get("type")

                    if payload_type == "custom_tool_call" and payload.get("name") == "apply_patch":
                        filename = extract_planning_file_from_patch(payload.get("input", ""))
                    elif payload_type == "function_call" and payload.get("name") == "exec_command":
                        filename = extract_planning_file_from_exec_command(payload.get("arguments", ""))

                if filename:
                    last_update_line = line_num
                    last_update_file = filename
    except OSError:
        pass

    return last_update_line, last_update_file


def extract_text_items(content) -> str:
    """Flatten message content blocks into a readable text string."""
    if isinstance(content, str):
        return content

    parts: List[str] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts).strip()


def summarize_codex_function_call(payload: Dict) -> Optional[str]:
    """Return a short human-readable description for Codex tool calls."""
    name = payload.get("name", "")
    if name == "exec_command":
        try:
            parsed = json.loads(payload.get("arguments", "{}"))
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            command = parsed.get("cmd", "")
            if isinstance(command, str) and command:
                return f"exec_command: {command[:80]}"
        return "exec_command"

    if name == "write_stdin":
        return "write_stdin"

    return name or None


def extract_messages_from_session(session_file: Path, after_line: int = -1) -> List[Dict]:
    """
    Extract conversation messages from a session file.
    If after_line >= 0, only extract messages after that line.
    If after_line < 0, extract all messages.
    """
    result: List[Dict] = []
    session_label = session_file.stem[:8]

    try:
        with open(session_file, "r", encoding="utf-8", errors="replace") as handle:
            for line_num, line in enumerate(handle):
                if after_line >= 0 and line_num <= after_line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                is_meta = msg.get("isMeta", False)

                if msg_type == "user" and not is_meta:
                    content = msg.get("message", {}).get("content", "")
                    content = extract_text_items(content)

                    if content and not content.startswith(("<local-command", "<command-", "<task-notification")):
                        result.append(
                            {
                                "role": "user",
                                "content": content,
                                "line": line_num,
                                "session": session_label,
                            }
                        )

                elif msg_type == "assistant":
                    text_content = ""
                    tool_uses: List[str] = []
                    msg_content = msg.get("message", {}).get("content", "")

                    if isinstance(msg_content, list):
                        for item in msg_content:
                            if item.get("type") == "text":
                                text_content = item.get("text", "")
                            elif item.get("type") == "tool_use":
                                tool_name = item.get("name", "")
                                tool_input = item.get("input", {})
                                if tool_name == "Edit":
                                    tool_uses.append(f"Edit: {tool_input.get('file_path', 'unknown')}")
                                elif tool_name == "Write":
                                    tool_uses.append(f"Write: {tool_input.get('file_path', 'unknown')}")
                                elif tool_name == "Bash":
                                    tool_uses.append(f"Bash: {tool_input.get('command', '')[:80]}")
                                elif tool_name == "AskUserQuestion":
                                    tool_uses.append("AskUserQuestion")
                                else:
                                    tool_uses.append(tool_name)
                    else:
                        text_content = extract_text_items(msg_content)

                    if text_content or tool_uses:
                        result.append(
                            {
                                "role": "assistant",
                                "content": text_content[:600] if text_content else "",
                                "tools": tool_uses,
                                "line": line_num,
                                "session": session_label,
                            }
                        )

                elif msg_type == "response_item":
                    payload = msg.get("payload", {})
                    payload_type = payload.get("type")

                    if payload_type == "message":
                        role = payload.get("role")
                        content = extract_text_items(payload.get("content", []))
                        if role in ("user", "assistant") and content:
                            entry = {
                                "role": role,
                                "content": content[:600] if role == "assistant" else content,
                                "line": line_num,
                                "session": session_label,
                            }
                            if role == "assistant":
                                entry["tools"] = []
                            result.append(entry)

                    elif payload_type == "function_call":
                        tool_summary = summarize_codex_function_call(payload)
                        if tool_summary:
                            result.append(
                                {
                                    "role": "assistant",
                                    "content": "",
                                    "tools": [tool_summary],
                                    "line": line_num,
                                    "session": session_label,
                                }
                            )
    except OSError:
        pass

    return result


def get_sessions_for_runtime(ide: str, project_path: str) -> List[Path]:
    """Return sorted session files for the active runtime."""
    if ide == "codex":
        return get_sessions_sorted_codex(project_path)

    if ide == "claude-code":
        project_dir = get_project_dir_claude(project_path)
        if not project_dir.exists():
            return []
        return get_sessions_sorted(project_dir)

    if ide == "opencode":
        project_dir = get_project_dir_opencode(project_path)
        if not project_dir:
            return []
        return get_sessions_sorted_opencode(project_dir)

    return []


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    has_planning_files = any(Path(project_path, filename).exists() for filename in PLANNING_FILES)
    if not has_planning_files:
        return

    ide = detect_ide()

    if ide == "opencode":
        print("\n[planning-with-files] OpenCode session catchup is not yet fully supported")
        print("OpenCode uses a different session storage format (.json) than Claude Code (.jsonl)")
        print("Session catchup requires parsing OpenCode's message storage structure.")
        print("\nWorkaround: Manually read task_plan.md, progress.md, and findings.md to catch up.")
        return

    sessions = get_sessions_for_runtime(ide, project_path)
    if len(sessions) < 2:
        return

    previous_sessions = sessions[1:]

    update_session = None
    update_line = -1
    update_file = None
    update_session_idx = -1

    for idx, session in enumerate(previous_sessions):
        line, filename = scan_for_planning_update(session)
        if line >= 0:
            update_session = session
            update_line = line
            update_file = filename
            update_session_idx = idx
            break

    if not update_session:
        return

    all_messages: List[Dict] = []
    all_messages.extend(extract_messages_from_session(update_session, after_line=update_line))

    intermediate_sessions = previous_sessions[:update_session_idx]
    for session in reversed(intermediate_sessions):
        all_messages.extend(extract_messages_from_session(session, after_line=-1))

    if not all_messages:
        return

    print(f"\n[planning-with-files] SESSION CATCHUP DETECTED (IDE: {ide})")
    print(f"Last planning update: {update_file} in session {update_session.stem[:8]}...")

    sessions_covered = update_session_idx + 1
    if sessions_covered > 1:
        print(f"Scanning {sessions_covered} sessions for unsynced context")

    print(f"Unsynced messages: {len(all_messages)}")
    print("\n--- UNSYNCED CONTEXT ---")

    max_messages = 100
    if len(all_messages) > max_messages:
        print(f"(Showing last {max_messages} of {len(all_messages)} messages)\n")
        messages_to_show = all_messages[-max_messages:]
    else:
        messages_to_show = all_messages

    assistant_label = "CLAUDE" if ide == "claude-code" else "ASSISTANT"
    current_session = None
    for msg in messages_to_show:
        if msg.get("session") != current_session:
            current_session = msg.get("session")
            print(f"\n[Session: {current_session}...]")

        if msg["role"] == "user":
            print(f"USER: {msg['content'][:300]}")
        else:
            if msg.get("content"):
                print(f"{assistant_label}: {msg['content'][:300]}")
            if msg.get("tools"):
                print(f"  Tools: {', '.join(msg['tools'][:4])}")

    print("\n--- RECOMMENDED ---")
    print("1. Run: git diff --stat")
    print("2. Read: task_plan.md, progress.md, findings.md")
    print("3. Update planning files based on above context")
    print("4. Continue with task")


if __name__ == "__main__":
    main()
