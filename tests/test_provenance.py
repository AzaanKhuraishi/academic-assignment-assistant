import json
import tempfile
import unittest
from pathlib import Path

from assignment_assistant.provenance import register_derivation
from assignment_assistant.intake import run_intake
from assignment_assistant.storage import WorkspaceError
from assignment_assistant.workspace import initialise_workspace


class ProvenanceTests(unittest.TestCase):
    def test_runtime_derivation_records_both_hashes_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            source = workspace / "source/lecture.mp4"
            derived = workspace / "derived/transcripts/lecture.md"
            source.write_bytes(b"synthetic-media")
            derived.write_text("Synthetic transcript", encoding="utf-8")
            first = register_derivation(
                workspace, source, derived, "test transcription", "checked"
            )
            second = register_derivation(
                workspace, source, derived, "test transcription", "checked"
            )
            self.assertEqual(first["source_sha256"], second["source_sha256"])
            payload = json.loads(
                (workspace / "assignment/research/derivation-provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(payload["records"]), 1)
            self.assertEqual(payload["records"][0]["verification_status"], "checked")

    def test_derivation_outside_derived_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            source = workspace / "source/lecture.mp4"
            bad_output = workspace / "assignment/working/transcript.md"
            source.write_bytes(b"synthetic-media")
            bad_output.write_text("Synthetic transcript", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceError, "inside workspace/derived"):
                register_derivation(workspace, source, bad_output, "test")

    def test_repeated_intake_preserves_registered_transcript(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            source = workspace / "source/lecture.mp4"
            derived = workspace / "derived/transcripts/lecture.md"
            source.write_bytes(b"synthetic-media")
            derived.write_text("Synthetic transcript", encoding="utf-8")
            register_derivation(workspace, source, derived, "test transcription", "checked")
            run_intake(workspace)
            payload = json.loads(
                (workspace / "assignment/research/derivation-provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(payload["records"]), 1)
            self.assertEqual(payload["records"][0]["method"], "test transcription")


if __name__ == "__main__":
    unittest.main()
