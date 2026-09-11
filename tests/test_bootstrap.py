import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from assignment_assistant.bootstrap import BootstrapError, ingest_source_path, main as bootstrap_main
from assignment_assistant.models import AssignmentPhase
from assignment_assistant.storage import load_state


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_registers_only_the_user_supplied_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            supplied = root / "brief.md"
            supplied.write_text("Explicit assignment brief", encoding="utf-8")

            self.assertEqual(
                bootstrap_main(
                    ["--workspace", str(workspace), "--source", str(supplied), "--start"]
                ),
                0,
            )

            state = load_state(workspace)
            self.assertEqual(state.phase, AssignmentPhase.BRIEFING_REQUIRED.value)
            self.assertEqual(state.registered_sources, ["source/brief.md"])

    def test_shared_pack_imports_inner_source_directory_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "shared-pack"
            (pack / "source/governing").mkdir(parents=True)
            (pack / "README.md").write_text("Pack instructions", encoding="utf-8")
            (pack / "source/governing/brief.md").write_text(
                "Assessment brief", encoding="utf-8"
            )
            workspace = root / "workspace"

            result = ingest_source_path(pack, workspace)

            self.assertEqual(result.copied, 1)
            self.assertTrue((workspace / "source/governing/brief.md").is_file())
            self.assertFalse((workspace / "source/README.md").exists())
            self.assertEqual(
                result.selected_files,
                [str((workspace / "source/governing/brief.md").resolve())],
            )

    def test_exact_copy_is_skipped_and_different_version_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            destination = workspace / "source/brief.md"
            destination.parent.mkdir(parents=True)
            destination.write_text("Version one", encoding="utf-8")

            exact = root / "exact/brief.md"
            exact.parent.mkdir()
            exact.write_text("Version one", encoding="utf-8")
            self.assertEqual(
                ingest_source_path(exact, workspace).skipped_exact,
                1,
            )

            changed = root / "changed/brief.md"
            changed.parent.mkdir()
            changed.write_text("Version two", encoding="utf-8")
            result = ingest_source_path(changed, workspace)

            self.assertEqual(result.renamed_conflicts, 1)
            self.assertEqual(destination.read_text(encoding="utf-8"), "Version one")
            preserved = list((workspace / "source").glob("brief--*.md"))
            self.assertEqual(len(preserved), 1)
            self.assertEqual(preserved[0].read_text(encoding="utf-8"), "Version two")

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../outside.txt", "unsafe")

            with self.assertRaisesRegex(BootstrapError, "unsafe path"):
                ingest_source_path(archive, root / "workspace")
            self.assertFalse((root / "outside.txt").exists())

    def test_zip_shared_pack_is_imported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "pack.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("pack/README.md", "Instructions")
                handle.writestr("pack/source/brief.md", "Assessment brief")

            result = ingest_source_path(archive, root / "workspace")

            self.assertEqual(result.copied, 1)
            self.assertEqual(
                (root / "workspace/source/brief.md").read_text(encoding="utf-8"),
                "Assessment brief",
            )

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows privileges")
    def test_direct_symbolic_link_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "brief.md"
            real.write_text("Assessment brief", encoding="utf-8")
            link = root / "linked-brief.md"
            link.symlink_to(real)

            with self.assertRaisesRegex(BootstrapError, "symbolic-link"):
                ingest_source_path(link, root / "workspace")


if __name__ == "__main__":
    unittest.main()
