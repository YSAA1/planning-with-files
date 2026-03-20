import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_SKILLS = REPO_ROOT / ".codex" / "skills"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = read_text(path)
    if not text.startswith("---\n"):
        return {}
    _, rest = text.split("---\n", 1)
    frontmatter, _ = rest.split("\n---\n", 1)
    result: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


class CodexManusCommandTests(unittest.TestCase):
    def test_planning_skill_is_no_longer_user_invocable(self):
        frontmatter = parse_frontmatter(
            CODEX_SKILLS / "planning-with-files" / "SKILL.md"
        )
        self.assertEqual("false", frontmatter.get("user-invocable"))

    def test_planning_skill_disables_implicit_invocation(self):
        config = read_text(
            CODEX_SKILLS / "planning-with-files" / "agents" / "openai.yaml"
        )
        self.assertIn("allow_implicit_invocation: false", config)

    def test_manus_wrapper_skills_exist(self):
        expected = {
            "manus-brainstorm",
            "manus-plan",
            "manus-status",
        }
        for name in expected:
            self.assertTrue((CODEX_SKILLS / name / "SKILL.md").exists(), name)
            self.assertTrue(
                (CODEX_SKILLS / name / "agents" / "openai.yaml").exists(), name
            )

    def test_manus_wrapper_skill_names_do_not_conflict_with_builtin_commands(self):
        reserved = {"plan", "plan-mode", "status", "review"}
        for name in ("manus-brainstorm", "manus-plan", "manus-status"):
            self.assertNotIn(name, reserved)

    def test_manus_brainstorm_explicit_only_and_no_file_creation(self):
        frontmatter = parse_frontmatter(CODEX_SKILLS / "manus-brainstorm" / "SKILL.md")
        config = read_text(CODEX_SKILLS / "manus-brainstorm" / "agents" / "openai.yaml")
        body = read_text(CODEX_SKILLS / "manus-brainstorm" / "SKILL.md")

        self.assertEqual("true", frontmatter.get("user-invocable"))
        self.assertIn("allow_implicit_invocation: false", config)
        self.assertIn("Brainstorm Summary", body)
        self.assertIn("Do not create `task_plan.md`", body)
        self.assertIn("Do not create `findings.md`", body)
        self.assertIn("Do not create `progress.md`", body)

    def test_manus_plan_is_a_soft_wrapper_not_a_copied_skill_body(self):
        body = read_text(CODEX_SKILLS / "manus-plan" / "SKILL.md")
        config = read_text(CODEX_SKILLS / "manus-plan" / "agents" / "openai.yaml")

        self.assertIn("allow_implicit_invocation: false", config)
        self.assertIn("Brainstorm Summary", body)
        self.assertIn("If there is no recent Brainstorm Summary", body)
        self.assertIn("ask the user whether to continue", body)
        self.assertIn("Invoke the `planning-with-files` skill", body)
        self.assertIn("follow it exactly as presented", body)
        self.assertNotIn("# Planning with Files", body)
        self.assertNotIn("templates/task_plan.md", body)

    def test_manus_status_reuses_planning_status_behavior(self):
        body = read_text(CODEX_SKILLS / "manus-status" / "SKILL.md")
        config = read_text(CODEX_SKILLS / "manus-status" / "agents" / "openai.yaml")

        self.assertIn("allow_implicit_invocation: false", config)
        self.assertIn("Read `task_plan.md`", body)
        self.assertIn("If no planning files exist", body)
        self.assertIn("/manus-brainstorm", body)
        self.assertIn("/manus-plan", body)

    def test_codex_docs_mention_new_explicit_flow(self):
        docs_text = read_text(REPO_ROOT / "docs" / "codex.md")
        self.assertIn("/manus-brainstorm", docs_text)
        self.assertIn("/manus-plan", docs_text)
        self.assertIn("/manus-status", docs_text)
        self.assertIn("allow_implicit_invocation: false", docs_text)

    def test_readme_mentions_codex_manus_commands(self):
        readme_text = read_text(REPO_ROOT / "README.md")
        self.assertRegex(readme_text, re.compile(r"/manus-brainstorm"))
        self.assertRegex(readme_text, re.compile(r"/manus-plan"))
        self.assertRegex(readme_text, re.compile(r"/manus-status"))


if __name__ == "__main__":
    unittest.main()
