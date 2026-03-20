import unittest
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_SKILLS = REPO_ROOT / ".codex" / "skills"
CODEX_AGENTS = REPO_ROOT / ".codex" / "agents"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_toml(path: Path) -> dict:
    return tomllib.loads(read_text(path))


class CodexSubagentWorkflowTests(unittest.TestCase):
    def test_codex_config_declares_parallel_limits(self):
        config = read_toml(REPO_ROOT / ".codex" / "config.toml")
        agents = config.get("agents", {})

        self.assertGreaterEqual(agents.get("max_threads", 0), 6)
        self.assertLessEqual(agents.get("max_threads", 99), 8)
        self.assertEqual(1, agents.get("max_depth"))

    def test_custom_agent_files_exist(self):
        expected = {
            "research.toml",
            "verification.toml",
            "review-test.toml",
        }

        for name in expected:
            self.assertTrue((CODEX_AGENTS / name).exists(), name)

    def test_custom_agents_are_readonly_and_have_required_fields(self):
        expected = {
            "research.toml": "research",
            "verification.toml": "verification",
            "review-test.toml": "review-test",
        }

        for filename, expected_name in expected.items():
            config = read_toml(CODEX_AGENTS / filename)
            self.assertEqual(expected_name, config.get("name"))
            self.assertTrue(config.get("description"))
            self.assertTrue(config.get("developer_instructions"))
            self.assertEqual("read-only", config.get("sandbox_mode"))

    def test_custom_agents_use_three_kingdoms_ascii_nicknames(self):
        expected = {
            "research.toml": ["Zhuge Liang", "Pang Tong", "Sima Hui"],
            "verification.toml": ["Zhao Yun", "Lu Meng", "Deng Ai"],
            "review-test.toml": ["Guan Yu", "Fa Zheng", "Jia Xu"],
        }

        for filename, nicknames in expected.items():
            config = read_toml(CODEX_AGENTS / filename)
            self.assertEqual(nicknames, config.get("nickname_candidates"))
            for nickname in nicknames:
                self.assertTrue(nickname.isascii(), nickname)

    def test_research_agent_has_openai_docs_mcp(self):
        config = read_toml(CODEX_AGENTS / "research.toml")
        mcp_servers = config.get("mcp_servers", {})
        docs_server = mcp_servers.get("openaiDeveloperDocs", {})

        self.assertEqual("https://developers.openai.com/mcp", docs_server.get("url"))

    def test_manus_plan_limits_subagents_to_post_planning_execution(self):
        body = read_text(CODEX_SKILLS / "manus-plan" / "SKILL.md")

        self.assertIn("subagent", body)
        self.assertIn("execution", body.lower())
        self.assertIn("may not edit code", body.lower())
        self.assertIn("may not write", body.lower())

    def test_planning_skill_declares_readonly_roles_and_main_agent_ownership(self):
        body = read_text(CODEX_SKILLS / "planning-with-files" / "SKILL.md")

        self.assertIn("research", body)
        self.assertIn("verification", body)
        self.assertIn("review-test", body)
        self.assertIn("main agent", body.lower())
        self.assertIn("task_plan.md", body)
        self.assertIn("findings.md", body)
        self.assertIn("progress.md", body)
        self.assertIn("scope checked", body.lower())
        self.assertIn("recommended next action", body.lower())

    def test_codex_docs_describe_readonly_subagent_workflow(self):
        docs = read_text(REPO_ROOT / "docs" / "codex.md")

        self.assertIn("readonly", docs.lower())
        self.assertIn("research", docs)
        self.assertIn("verification", docs)
        self.assertIn("review-test", docs)

    def test_readme_mentions_main_agent_owns_writes(self):
        readme = read_text(REPO_ROOT / "README.md")

        self.assertIn("main agent", readme.lower())
        self.assertIn("planning files", readme.lower())

    def test_troubleshooting_warns_subagents_not_to_write_planning_files(self):
        troubleshooting = read_text(REPO_ROOT / "docs" / "troubleshooting.md")

        self.assertIn("subagent", troubleshooting.lower())
        self.assertIn("should not write planning files", troubleshooting.lower())
        self.assertIn("main agent", troubleshooting.lower())


if __name__ == "__main__":
    unittest.main()
