import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assignment_assistant.configuration import DEFAULT_CONFIG
from assignment_assistant.models import AssignmentPhase, SliceStatus
from assignment_assistant.orchestration import (
    TransitionError,
    accept_slice,
    add_slice,
    advance_slice,
    approve_gate,
    begin_final_validation,
    mark_ready_for_handoff,
    record_intake,
    record_source_freshness_answer,
    record_source_update,
    reject_slice,
    require_source_freshness_if_due,
    require_user_input,
    resolve_user_input,
    resolve_source_impact,
    submit_architecture,
    submit_briefing,
)
from assignment_assistant.storage import WorkspaceError
from assignment_assistant.validation import validate_workspace_for_final
from assignment_assistant.workspace import initialise_workspace


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "assignment"
        self.state = initialise_workspace(self.workspace)
        record_intake(
            self.state,
            dict(DEFAULT_CONFIG),
            "assignment/research/source-manifest.json",
            "SOURCE_INDEX.md",
            {"discipline": "consultancy", "requires_confirmation": False},
            ["source/brief.md"],
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _approve_architecture(self):
        briefing = self.workspace / "assignment/briefing/ASSESSMENT_BRIEFING.md"
        briefing.write_text("Approved interpretation", encoding="utf-8")
        submit_briefing(self.state, self.workspace, briefing)
        approve_gate(self.state, "gate1", "user")
        architecture = self.workspace / "assignment/working/ASSIGNMENT_ARCHITECTURE.md"
        architecture.write_text("Approved architecture", encoding="utf-8")
        submit_architecture(self.state, self.workspace, architecture)
        approve_gate(self.state, "gate2", "user")

    def test_gates_cannot_be_bypassed(self):
        with self.assertRaises(TransitionError):
            approve_gate(self.state, "gate1", "user")
        with self.assertRaises(TransitionError):
            add_slice(self.state, "s1", "Premature slice")

    def test_artifacts_must_stay_inside_workspace(self):
        outside = Path(self.temporary.name) / "outside.md"
        outside.write_text("not allowed", encoding="utf-8")
        with self.assertRaises(WorkspaceError):
            submit_briefing(self.state, self.workspace, outside)

    def test_complete_vertical_slice_and_final_handoff(self):
        self._approve_architecture()
        add_slice(self.state, "s1", "Diagnosis", ["critical analysis"], 500)
        artifact = self.workspace / "assignment/working/s1.md"
        artifact.write_text("Checked slice artefact", encoding="utf-8")
        for status in list(SliceStatus)[1:]:
            if status == SliceStatus.ACCEPTED:
                accept_slice(self.state, "s1", "user", "Approved")
            else:
                advance_slice(self.state, self.workspace, "s1", status.value, artifact)
        self.assertEqual(self.state.slices["s1"].status, SliceStatus.INTEGRATED.value)

        begin_final_validation(self.state)
        final = self.workspace / "assignment/final/report.md"
        final.write_text("A complete fictional report.", encoding="utf-8")
        report = validate_workspace_for_final(self.workspace, self.state)
        self.assertTrue(report["passed"])
        report_path = self.workspace / "assignment/final/quality-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        mark_ready_for_handoff(
            self.state, report_path.relative_to(self.workspace).as_posix()
        )
        self.assertEqual(self.state.phase, AssignmentPhase.READY_FOR_HANDOFF.value)

    def test_rejection_routes_and_retry_escalation(self):
        self._approve_architecture()
        self.state.config["max_autonomous_retries"] = 1
        add_slice(self.state, "s1", "Evidence test")
        artifact = self.workspace / "assignment/working/s1.md"
        artifact.write_text("Test artifact", encoding="utf-8")
        advance_slice(self.state, self.workspace, "s1", "RESEARCHED", artifact)
        advance_slice(self.state, self.workspace, "s1", "EVIDENCED", artifact)
        advance_slice(self.state, self.workspace, "s1", "ANALYSED", artifact)
        reject_slice(self.state, "s1", "citation_problem", "Page is wrong")
        self.assertEqual(self.state.slices["s1"].status, SliceStatus.EVIDENCED.value)
        reject_slice(self.state, "s1", "citation_problem", "Source is still unsupported")
        self.assertEqual(self.state.phase, AssignmentPhase.REQUIRES_USER_INPUT.value)
        self.assertEqual(len([item for item in self.state.user_inputs if item.status == "open"]), 1)

    def test_slice_acceptance_requires_user_review(self):
        self._approve_architecture()
        add_slice(self.state, "s1", "Review boundary")
        with self.assertRaisesRegex(TransitionError, "cannot be accepted"):
            accept_slice(self.state, "s1", "user")

    def test_rejection_cannot_move_a_slice_forward(self):
        self._approve_architecture()
        add_slice(self.state, "s1", "Failure direction")
        with self.assertRaisesRegex(TransitionError, "move.*forward"):
            reject_slice(self.state, "s1", "citation_problem", "Premature check")
        self.assertEqual(self.state.slices["s1"].retry_counts, {})
        self.assertEqual(self.state.slices["s1"].status, SliceStatus.PLANNED.value)

    def test_authentic_input_pause_resumes_exact_phase(self):
        self._approve_architecture()
        request = require_user_input(self.state, "Describe your seminar contribution")
        self.assertEqual(self.state.phase, AssignmentPhase.REQUIRES_USER_INPUT.value)
        resolve_user_input(self.state, request.request_id, "I challenged the initial scope.")
        self.assertEqual(self.state.phase, AssignmentPhase.EXECUTION.value)

    def test_source_freshness_gate_pauses_and_resumes_exact_phase(self):
        self._approve_architecture()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.state.last_substantive_activity_at = (now - timedelta(hours=6)).isoformat()

        self.assertTrue(require_source_freshness_if_due(self.state, 6, now))
        self.assertEqual(self.state.phase, AssignmentPhase.SOURCE_FRESHNESS_REQUIRED.value)
        self.assertEqual(self.state.freshness_resume_phase, AssignmentPhase.EXECUTION.value)

        record_source_freshness_answer(self.state, False)
        self.assertEqual(self.state.phase, AssignmentPhase.EXECUTION.value)
        self.assertIsNone(self.state.freshness_resume_phase)

    def test_source_update_requires_impact_and_can_reopen_briefing(self):
        briefing = self.workspace / "assignment/briefing/ASSESSMENT_BRIEFING.md"
        briefing.write_text("Old briefing", encoding="utf-8")
        submit_briefing(self.state, self.workspace, briefing)
        self.state.last_substantive_activity_at = "2026-01-01T00:00:00+00:00"
        now = datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)
        require_source_freshness_if_due(self.state, 6, now)
        record_source_freshness_answer(self.state, True)
        record_source_update(
            self.state,
            "assignment/research/source-manifest.json",
            "SOURCE_INDEX.md",
            {"discipline": "consultancy", "requires_confirmation": False},
            ["source/brief.md", "source/updated-rubric.md"],
            "assignment/research/source-change.json",
            {"added": ["source/updated-rubric.md"], "updated": [], "removed": []},
        )
        self.assertEqual(self.state.phase, AssignmentPhase.SOURCE_IMPACT_REQUIRED.value)

        impact = self.workspace / "assignment/research/SOURCE_IMPACT.md"
        impact.write_text("The revised rubric changes assessed requirements.", encoding="utf-8")
        resolve_source_impact(self.state, self.workspace, impact, "briefing")
        self.assertEqual(self.state.phase, AssignmentPhase.BRIEFING_REQUIRED.value)
        self.assertIsNone(self.state.briefing_artifact)


if __name__ == "__main__":
    unittest.main()
