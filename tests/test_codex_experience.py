import unittest
from pathlib import Path


class CodexExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = Path(__file__).resolve().parents[1]

    def test_readme_leads_with_nontechnical_codex_quick_start(self):
        readme = (self.repository / "README.md").read_text(encoding="utf-8")
        quick_start = readme.index("## Codex Quick Start")
        advanced = readme.index("## Advanced / Local / Developer Setup")
        self.assertLess(quick_start, advanced)
        self.assertNotIn("python3 -m venv", readme[quick_start:advanced])
        self.assertIn("Set up Academic Assignment Assistant", readme[quick_start:advanced])

    def test_agents_contract_bootstraps_and_hides_cli_from_student(self):
        instructions = (self.repository / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("scripts/codex_bootstrap.py", instructions)
        self.assertIn("Do not ask the user to create a Python", instructions)
        self.assertIn("docs/codex-operations.md", instructions)
        self.assertIn("Do not weaken a gate", instructions)
        self.assertIn("Do not inspect or register them unless the user explicitly selects them", instructions)
        self.assertIn("six hours of inactivity", instructions)

    def test_bootstrap_script_is_available_from_a_fresh_checkout(self):
        script = self.repository / "scripts/codex_bootstrap.py"
        self.assertTrue(script.is_file())
        self.assertIn(
            "assignment_assistant.bootstrap",
            script.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
