import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from assignment_assistant.models import Approval, AssignmentState, SliceRecord, SliceStatus
from assignment_assistant.validation import validate_text_artifact, validate_workspace_for_final


class ValidationTests(unittest.TestCase):
    def test_unresolved_markers_are_blockers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "draft.md"
            path.write_text("Claim. [EVIDENCE GAP]\nTODO: verify", encoding="utf-8")
            report = validate_text_artifact(path)
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["findings"]), 2)

    def test_plain_complete_text_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "draft.md"
            path.write_text("A checked analytical paragraph.", encoding="utf-8")
            report = validate_text_artifact(path)
        self.assertTrue(report["passed"])

    def test_layout_output_requires_recorded_visual_inspection(self):
        now = datetime.now(timezone.utc).isoformat()
        state = AssignmentState(
            schema_version=1,
            assignment_id="00000000-0000-0000-0000-000000000001",
            created_at=now,
            updated_at=now,
            briefing_artifact="assignment/briefing/briefing.md",
            architecture_artifact="assignment/working/architecture.md",
            approvals=[
                Approval("gate1", now, "user"),
                Approval("gate2", now, "user"),
            ],
            slices={
                "s1": SliceRecord(
                    "s1", "Complete slice", status=SliceStatus.INTEGRATED.value
                )
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            final_dir = workspace / "assignment/final"
            final_dir.mkdir(parents=True)
            deliverable = final_dir / "report.pdf"
            deliverable.write_bytes(b"%PDF-1.4 synthetic test")
            report = validate_workspace_for_final(workspace, state)
            self.assertFalse(report["passed"])

            relative = deliverable.relative_to(workspace).as_posix()
            (final_dir / "visual-inspection.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "inspected_at": now,
                        "inspected_files": [relative],
                        "notes": "Rendered and checked",
                    }
                ),
                encoding="utf-8",
            )
            report = validate_workspace_for_final(workspace, state)
            self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
