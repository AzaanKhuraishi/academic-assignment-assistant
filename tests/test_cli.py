import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assignment_assistant.cli import main
from assignment_assistant.models import AssignmentPhase
from assignment_assistant.storage import load_state, save_state


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
            code, output, _ = self.call(
                ["start", str(workspace), "--source", "source/brief.md"]
            )
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
            self.assertEqual(
                self.call(["start", str(workspace), "--source", "source/brief.md"])[0],
                0,
            )
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

    def test_initial_intake_indexes_only_explicitly_selected_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            self.assertEqual(self.call(["init", str(workspace)])[0], 0)
            (workspace / "source/selected.md").write_text("Selected brief", encoding="utf-8")
            (workspace / "source/ambient.md").write_text("Partial old material", encoding="utf-8")

            code, _, error = self.call(
                ["start", str(workspace), "--source", "source/selected.md"]
            )

            self.assertEqual(code, 0, error)
            state = load_state(workspace)
            self.assertEqual(state.registered_sources, ["source/selected.md"])
            manifest = json.loads((workspace / state.source_manifest).read_text(encoding="utf-8"))
            self.assertEqual([item["path"] for item in manifest["records"]], ["source/selected.md"])

    def test_six_hour_resume_gate_supports_incremental_update_and_impact(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            self.assertEqual(self.call(["init", str(workspace)])[0], 0)
            (workspace / "source/brief.md").write_text("Original brief", encoding="utf-8")
            self.assertEqual(
                self.call(["start", str(workspace), "--source", "source/brief.md"])[0],
                0,
            )
            state = load_state(workspace)
            original_phase = state.phase
            state.last_substantive_activity_at = (
                datetime.now(timezone.utc) - timedelta(hours=6, minutes=1)
            ).replace(microsecond=0).isoformat()
            save_state(workspace, state)

            self.assertEqual(self.call(["next-task", str(workspace)])[0], 0)
            self.assertEqual(
                load_state(workspace).phase,
                AssignmentPhase.SOURCE_FRESHNESS_REQUIRED.value,
            )
            self.assertEqual(self.call(["source-freshness", str(workspace), "yes"])[0], 0)
            (workspace / "source/new-guidance.md").write_text(
                "New module guidance", encoding="utf-8"
            )
            code, output, error = self.call(
                [
                    "refresh-sources",
                    str(workspace),
                    "--source",
                    "source/new-guidance.md",
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertIn('"source/new-guidance.md"', output)
            state = load_state(workspace)
            self.assertEqual(state.phase, AssignmentPhase.SOURCE_IMPACT_REQUIRED.value)
            self.assertEqual(
                state.registered_sources,
                ["source/brief.md", "source/new-guidance.md"],
            )

            impact = workspace / "assignment/research/SOURCE_IMPACT.md"
            impact.write_text("No existing work is affected.", encoding="utf-8")
            self.assertEqual(
                self.call(
                    [
                        "resolve-source-impact",
                        str(workspace),
                        "assignment/research/SOURCE_IMPACT.md",
                        "none",
                    ]
                )[0],
                0,
            )
            self.assertEqual(load_state(workspace).phase, original_phase)


if __name__ == "__main__":
    unittest.main()
