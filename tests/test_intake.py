import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from assignment_assistant.intake import run_intake
from assignment_assistant.routing import route_subject
from assignment_assistant.storage import WorkspaceError
from assignment_assistant.workspace import initialise_workspace


class IntakeTests(unittest.TestCase):
    def test_empty_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            with self.assertRaisesRegex(WorkspaceError, "No source files"):
                run_intake(workspace)

    def test_hash_deduplication_and_consultancy_routing(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            source = workspace / "source"
            content = "Assessment brief: consultancy client stakeholder soft systems SSM CATWOE"
            (source / "brief.md").write_text(content, encoding="utf-8")
            (source / "copied-brief.md").write_text(content, encoding="utf-8")

            result = run_intake(workspace)
            manifest = result["manifest"]
            self.assertEqual(manifest["source_count"], 2)
            self.assertEqual(manifest["unique_hash_count"], 1)
            self.assertEqual(manifest["duplicate_count"], 1)
            duplicate = next(record for record in manifest["records"] if record["duplicate_of"])
            self.assertEqual(duplicate["extraction_status"], "duplicate-skipped")

            routing = route_subject(result["routing_text"])
            self.assertEqual(routing["discipline"], "consultancy")
            self.assertFalse(routing["requires_confirmation"])

    def test_docx_creates_provenanced_reading_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "assignment"
            initialise_workspace(workspace)
            document = workspace / "source" / "Assessment Brief.docx"
            with zipfile.ZipFile(document, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    "<w:document><w:body><w:p><w:t>Learning outcomes and rubric</w:t>"
                    "</w:p></w:body></w:document>",
                )

            result = run_intake(workspace)
            record = result["manifest"]["records"][0]
            self.assertEqual(record["extraction_status"], "derived-xml")
            reading_copy = workspace / record["reading_copy"]
            self.assertTrue(reading_copy.exists())
            self.assertIn(record["sha256"], reading_copy.read_text(encoding="utf-8"))
            provenance = json.loads(
                (workspace / "assignment/research/derivation-provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(provenance["records"][0]["source_sha256"], record["sha256"])


if __name__ == "__main__":
    unittest.main()
