import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from assignment_assistant.cli import main
from assignment_assistant.models import AssignmentPhase
from assignment_assistant.storage import load_state


class CliIntegrationTests(unittest.TestCase):
    def call(self, arguments):
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            result = main(arguments)
        return result, output.getvalue(), error.getvalue()

    def test_intake_and_two_gate_flow_persists(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            self.assertEqual(self.call(["init", str(workspace)])[0], 0)
            (workspace / "source/brief.md").write_text(
                "A consultancy client assignment using SSM and stakeholder analysis.",
                encoding="utf-8",
            )
            code, output, _ = self.call(["start", str(workspace)])
            self.assertEqual(code, 0)
            self.assertIn("Discipline suggestion: consultancy", output)

            briefing = workspace / "assignment/briefing/briefing.md"
            briefing.write_text("Checked briefing", encoding="utf-8")
            self.assertEqual(
                self.call(
                    ["submit-briefing", str(workspace), "assignment/briefing/briefing.md"]
                )[0],
                0,
            )
            self.assertEqual(self.call(["approve", str(workspace), "gate1"])[0], 0)

            architecture = workspace / "assignment/working/architecture.md"
            architecture.write_text("Checked architecture", encoding="utf-8")
            self.assertEqual(
                self.call(
                    [
                        "submit-architecture",
                        str(workspace),
                        "assignment/working/architecture.md",
                    ]
                )[0],
                0,
            )
            self.assertEqual(self.call(["approve", str(workspace), "gate2"])[0], 0)
            self.assertEqual(load_state(workspace).phase, AssignmentPhase.EXECUTION.value)

    def test_confirm_discipline_updates_state_and_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            self.assertEqual(self.call(["init", str(workspace)])[0], 0)
            (workspace / "source/brief.md").write_text(
                "Write an assessed report from the supplied material.", encoding="utf-8"
            )
            self.assertEqual(self.call(["start", str(workspace)])[0], 0)
            state = load_state(workspace)
            self.assertTrue(state.routing["requires_confirmation"])
            self.assertEqual(
                self.call(
                    ["confirm-discipline", str(workspace), "humanities"]
                )[0],
                0,
            )
            state = load_state(workspace)
            self.assertEqual(state.routing["discipline"], "humanities")
            self.assertFalse(state.routing["requires_confirmation"])
            self.assertIn(
                "discipline: humanities",
                (workspace / "assignment-assistant.yaml").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
