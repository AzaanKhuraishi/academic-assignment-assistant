import tempfile
import unittest
from pathlib import Path

from assignment_assistant.workspace import initialise_workspace


class WorkspaceTests(unittest.TestCase):
    def test_initialisation_creates_private_workflow_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            template_dir = workspace / ".assignment-assistant/templates"
            expected = {
                "assessment-briefing.md",
                "assignment-architecture.md",
                "authentic-user-input.md",
                "evidence-matrix.md",
                "research-log.md",
                "vertical-slice.md",
                "visual-inspection.json",
            }
            self.assertEqual({path.name for path in template_dir.iterdir()}, expected)
            self.assertEqual(list((workspace / "source").iterdir()), [])
            self.assertTrue((workspace / ".assignment-assistant/capabilities.json").exists())


if __name__ == "__main__":
    unittest.main()
