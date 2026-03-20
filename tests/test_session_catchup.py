import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_SOURCE = Path(__file__).resolve().parents[1] / "scripts/session-catchup.py"


def load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(
        f"session_catchup_{script_path.stat().st_mtime_ns}",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


class SessionCatchupCodexTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project_dir = self.root / "project"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        (self.project_dir / "task_plan.md").write_text("# active plan\n", encoding="utf-8")

        self.codex_script = (
            self.root / ".codex/skills/planning-with-files/scripts/session-catchup.py"
        )
        self.codex_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT_SOURCE, self.codex_script)
        self.module = load_module(self.codex_script)

    def tearDown(self):
        self.tempdir.cleanup()

    def session_meta(self, *, source=None):
        payload = {
            "id": "session-id",
            "cwd": str(self.project_dir),
            "originator": "codex-tui",
        }
        if source is not None:
            payload["source"] = source
        return {
            "timestamp": "2026-03-20T10:00:00.000Z",
            "type": "session_meta",
            "payload": payload,
        }

    def response_message(self, role: str, text: str):
        return {
            "timestamp": "2026-03-20T10:00:01.000Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": role,
                "content": [{"type": "output_text" if role == "assistant" else "input_text", "text": text}],
            },
        }

    def response_function_call(self, name: str, arguments: str):
        return {
            "timestamp": "2026-03-20T10:00:02.000Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": name,
                "arguments": arguments,
                "call_id": "call-id",
            },
        }

    def response_custom_tool_call(self, name: str, tool_input: str):
        return {
            "timestamp": "2026-03-20T10:00:03.000Z",
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "status": "completed",
                "call_id": "call-id",
                "name": name,
                "input": tool_input,
            },
        }

    def event_agent_message(self, text: str):
        return {
            "timestamp": "2026-03-20T10:00:04.000Z",
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": text,
            },
        }

    def create_session(self, relative_path: str, records, *, mtime: int):
        session_path = self.root / ".codex" / "sessions" / relative_path
        write_jsonl(session_path, records)
        session_path.touch()
        session_path.chmod(0o644)
        Path(session_path).touch()
        import os
        os.utime(session_path, (mtime, mtime))
        return session_path

    def test_codex_scan_for_planning_update_detects_apply_patch(self):
        session_path = self.create_session(
            "2026/03/20/rollout-apply-patch.jsonl",
            [
                self.session_meta(),
                self.response_custom_tool_call(
                    "apply_patch",
                    "*** Begin Patch\n"
                    "*** Add File: task_plan.md\n"
                    "+hello\n"
                    "*** End Patch\n",
                ),
            ],
            mtime=100,
        )

        line, filename = self.module.scan_for_planning_update(session_path)

        self.assertEqual(1, line)
        self.assertEqual("task_plan.md", filename)

    def test_codex_primary_session_accepts_string_source(self):
        self.assertTrue(self.module.is_codex_primary_session({"source": "cli"}))

    def test_sanitize_project_path_preserves_leading_dash_for_absolute_paths(self):
        sanitized = self.module.sanitize_project_path("/tmp/project")
        self.assertEqual("-tmp-project", sanitized)

    def test_codex_scan_for_planning_update_detects_exec_command_write(self):
        session_path = self.create_session(
            "2026/03/20/rollout-exec-write.jsonl",
            [
                self.session_meta(),
                self.response_function_call(
                    "exec_command",
                    json.dumps(
                        {
                            "cmd": f"cat > {self.project_dir / 'progress.md'} <<'EOF'\nprogress\nEOF",
                            "workdir": str(self.project_dir),
                        }
                    ),
                ),
            ],
            mtime=100,
        )

        line, filename = self.module.scan_for_planning_update(session_path)

        self.assertEqual(1, line)
        self.assertEqual("progress.md", filename)

    def test_codex_scan_for_planning_update_ignores_read_only_mentions(self):
        session_path = self.create_session(
            "2026/03/20/rollout-read-only.jsonl",
            [
                self.session_meta(),
                self.response_function_call(
                    "exec_command",
                    json.dumps(
                        {
                            "cmd": "sed -n '1,120p' task_plan.md",
                            "workdir": str(self.project_dir),
                        }
                    ),
                ),
            ],
            mtime=100,
        )

        line, filename = self.module.scan_for_planning_update(session_path)

        self.assertEqual(-1, line)
        self.assertIsNone(filename)

    def test_codex_extract_messages_ignores_event_agent_message_duplicates(self):
        session_path = self.create_session(
            "2026/03/20/rollout-messages.jsonl",
            [
                self.session_meta(),
                self.response_message("user", "please continue"),
                self.response_message("assistant", "working on it"),
                self.event_agent_message("working on it"),
            ],
            mtime=100,
        )

        messages = self.module.extract_messages_from_session(session_path, after_line=-1)

        self.assertEqual(
            [
                {
                    "role": "user",
                    "content": "please continue",
                    "line": 1,
                    "session": "rollout-",
                },
                {
                    "role": "assistant",
                    "content": "working on it",
                    "tools": [],
                    "line": 2,
                    "session": "rollout-",
                },
            ],
            messages,
        )

    def test_codex_main_collects_previous_main_sessions_only(self):
        self.create_session(
            "2026/03/20/rollout-older-update.jsonl",
            [
                self.session_meta(),
                self.response_custom_tool_call(
                    "apply_patch",
                    "*** Begin Patch\n"
                    "*** Update File: findings.md\n"
                    "@@\n"
                    "+note\n"
                    "*** End Patch\n",
                ),
                self.response_message("user", "older follow-up"),
                self.response_message("assistant", "older answer"),
            ],
            mtime=100,
        )
        self.create_session(
            "2026/03/20/rollout-previous-main.jsonl",
            [
                self.session_meta(),
                self.response_message("user", "previous main question"),
                self.response_message("assistant", "previous main answer"),
            ],
            mtime=200,
        )
        self.create_session(
            "2026/03/20/rollout-current-main.jsonl",
            [
                self.session_meta(),
                self.response_message("user", "current main question"),
                self.response_message("assistant", "current main answer"),
            ],
            mtime=300,
        )
        self.create_session(
            "2026/03/20/rollout-subagent.jsonl",
            [
                self.session_meta(source={"subagent": {"other": "guardian"}}),
                self.response_message("assistant", "subagent output"),
            ],
            mtime=400,
        )

        stdout = io.StringIO()
        with mock.patch("pathlib.Path.home", return_value=self.root):
            with mock.patch.object(self.module.sys, "argv", ["session-catchup.py", str(self.project_dir)]):
                with contextlib.redirect_stdout(stdout):
                    self.module.main()

        output = stdout.getvalue()
        self.assertIn("SESSION CATCHUP DETECTED (IDE: codex)", output)
        self.assertIn("older follow-up", output)
        self.assertIn("previous main question", output)
        self.assertNotIn("current main question", output)
        self.assertNotIn("subagent output", output)


if __name__ == "__main__":
    unittest.main()
