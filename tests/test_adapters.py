import tempfile
import unittest
from pathlib import Path

from assignment_assistant.adapters.codex import CodexAdapter
from assignment_assistant.configuration import DEFAULT_CONFIG
from assignment_assistant.orchestration import (
    add_slice,
    approve_gate,
    record_intake,
    submit_architecture,
    submit_briefing,
)
from assignment_assistant.workspace import initialise_workspace


class CodexAdapterTests(unittest.TestCase):
    def test_briefing_packet_names_contract_overlay_and_record_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            state = initialise_workspace(workspace)
            record_intake(
                state,
                dict(DEFAULT_CONFIG),
                "assignment/research/source-manifest.json",
                "SOURCE_INDEX.md",
                {"discipline": "consultancy"},
            )
            packet = CodexAdapter().render_next_task(workspace, state)
        self.assertIn("agents/contracts/brief-interpreter.md", packet)
        self.assertIn("overlays/consultancy.md", packet)
        self.assertIn("submit-briefing", packet)
        self.assertIn("Do not ask the user to run", packet)
        self.assertIn("-m assignment_assistant submit-briefing", packet)

    def test_planned_slice_selects_research_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            state = initialise_workspace(workspace)
            record_intake(
                state,
                dict(DEFAULT_CONFIG),
                "manifest.json",
                "SOURCE_INDEX.md",
                {"discipline": "generic"},
            )
            briefing = workspace / "assignment/briefing/briefing.md"
            briefing.write_text("Briefing", encoding="utf-8")
            submit_briefing(state, workspace, briefing)
            approve_gate(state, "gate1", "user")
            architecture = workspace / "assignment/working/architecture.md"
            architecture.write_text("Architecture", encoding="utf-8")
            submit_architecture(state, workspace, architecture)
            approve_gate(state, "gate2", "user")
            add_slice(state, "s1", "Synthetic slice")
            packet = CodexAdapter().render_next_task(workspace, state)
        self.assertIn("agents/contracts/researcher.md", packet)
        self.assertIn("slice 's1'", packet)

    def test_weak_routing_stops_for_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            state = initialise_workspace(workspace)
            record_intake(
                state,
                dict(DEFAULT_CONFIG),
                "manifest.json",
                "SOURCE_INDEX.md",
                {
                    "discipline": "cybersecurity",
                    "requires_confirmation": True,
                    "scores": {"cybersecurity": 1},
                },
            )
            packet = CodexAdapter().render_next_task(workspace, state)
        self.assertIn("agents/contracts/subject-router.md", packet)
        self.assertIn("confirm-discipline", packet)
        self.assertNotIn("submit-briefing", packet)


if __name__ == "__main__":
    unittest.main()
