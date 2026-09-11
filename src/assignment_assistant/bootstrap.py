"""Reliable, idempotent bootstrap used by the Codex conversational adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import venv
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import List, Optional, Sequence


MINIMUM_PYTHON = (3, 9)
MAX_ARCHIVE_MEMBERS = 50_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024


class BootstrapError(RuntimeError):
    """A setup problem that Codex can explain without exposing a traceback."""


@dataclass
class IngestResult:
    copied: int = 0
    skipped_exact: int = 0
    renamed_conflicts: int = 0
    selected_files: List[str] = field(default_factory=list)

    def add(self, other: "IngestResult") -> None:
        self.copied += other.copied
        self.skipped_exact += other.skipped_exact
        self.renamed_conflicts += other.renamed_conflicts
        self.selected_files.extend(other.selected_files)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def virtualenv_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _last_detail(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in (stderr + "\n" + stdout).splitlines() if line.strip()]
    return lines[-1] if lines else "No further detail was provided."


def _run(command: Sequence[str], description: str, cwd: Path) -> str:
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        check=False,
    )
    if completed.returncode != 0:
        detail = _last_detail(completed.stdout, completed.stderr)
        raise BootstrapError(f"Codex could not {description}. Technical detail: {detail}")
    return completed.stdout.strip()


def _command_succeeds(command: Sequence[str], cwd: Path) -> bool:
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _install_local_import_path(interpreter: Path, repository: Path) -> None:
    """Make the source checkout importable when an old offline pip cannot do PEP 660."""

    purelib = _run(
        (
            str(interpreter),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ),
        "locate the private Python environment",
        repository,
    )
    target = Path(purelib) / "academic_assignment_assistant_local.pth"
    try:
        target.write_text(str(repository / "src") + "\n", encoding="utf-8")
    except OSError as exc:
        raise BootstrapError(
            "Codex could not make the local Assignment Assistant engine available."
        ) from exc


def ensure_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        raise BootstrapError(
            f"Automatic setup needs Python {required} or later; this launcher is Python {current}."
        )


def ensure_environment(repository: Path, environment: Path) -> Path:
    """Create the private environment if needed and install the local checkout."""

    ensure_supported_python()
    interpreter = virtualenv_python(environment)
    if not interpreter.is_file():
        try:
            venv.EnvBuilder(with_pip=True, clear=False, upgrade=False).create(environment)
        except (OSError, subprocess.SubprocessError) as exc:
            raise BootstrapError(
                "Codex could not prepare the private working environment. "
                "The repository and assignment files were not changed."
            ) from exc
    if not interpreter.is_file():
        raise BootstrapError(
            "The private working environment is incomplete. The repository and assignment "
            "files were not changed."
        )
    import_check = (str(interpreter), "-c", "import assignment_assistant")
    if not _command_succeeds(import_check, repository):
        try:
            _run(
                (
                    str(interpreter),
                    "-m",
                    "pip",
                    "install",
                    "--quiet",
                    "--no-input",
                    "-e",
                    str(repository),
                ),
                "install the local Assignment Assistant engine",
                repository,
            )
        except BootstrapError:
            # Older platform-managed Python installations can ship a pip that cannot
            # perform a modern editable install. The .pth fallback is local,
            # dependency-free and still executes this checkout directly.
            _install_local_import_path(interpreter, repository)
    if not _command_succeeds(import_check, repository):
        raise BootstrapError(
            "Codex could not make the local Assignment Assistant engine available."
        )
    return interpreter


def ensure_workspace(interpreter: Path, repository: Path, workspace: Path) -> bool:
    """Initialise a workspace once. Existing workflow state is never replaced."""

    state_path = workspace / ".assignment-assistant" / "state.json"
    if state_path.is_file():
        return False
    _run(
        (str(interpreter), "-m", "assignment_assistant", "init", str(workspace)),
        "create the private assignment workspace",
        repository,
    )
    return True


def _is_hidden_or_temporary(relative: Path) -> bool:
    return any(part.startswith(".") for part in relative.parts) or relative.name.startswith("~$")


def _safe_destination(root: Path, relative: Path) -> Path:
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise BootstrapError("A supplied source path would escape the private workspace.") from exc
    return target


def _conflict_name(path: Path, digest: str, attempt: int = 1) -> Path:
    suffix = "".join(path.suffixes)
    base = path.name[: -len(suffix)] if suffix else path.name
    counter = "" if attempt == 1 else f"-{attempt}"
    return path.with_name(f"{base}--{digest[:8]}{counter}{suffix}")


def _copy_source_file(source: Path, destination: Path, source_root: Path) -> IngestResult:
    if source.is_symlink():
        raise BootstrapError(f"The source contains a symbolic link that was not imported: {source}")
    _safe_destination(source_root, destination.relative_to(source_root))
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_digest = sha256_file(source)
    if destination.exists():
        if not destination.is_file():
            raise BootstrapError(f"A source file conflicts with an existing folder: {destination.name}")
        if sha256_file(destination) == source_digest:
            return IngestResult(skipped_exact=1, selected_files=[str(destination)])
        attempt = 1
        candidate = _conflict_name(destination, source_digest, attempt)
        while candidate.exists():
            if candidate.is_file() and sha256_file(candidate) == source_digest:
                return IngestResult(skipped_exact=1, selected_files=[str(candidate)])
            attempt += 1
            candidate = _conflict_name(destination, source_digest, attempt)
        destination = candidate
        renamed = 1
    else:
        renamed = 0
    shutil.copy2(source, destination)
    return IngestResult(
        copied=1,
        renamed_conflicts=renamed,
        selected_files=[str(destination)],
    )


def _select_payload_root(root: Path) -> Path:
    direct = root / "source"
    if direct.is_dir():
        return direct
    nested = sorted(
        child / "source"
        for child in root.iterdir()
        if child.is_dir() and not child.is_symlink() and (child / "source").is_dir()
    )
    if len(nested) == 1:
        return nested[0]
    return root


def _copy_source_tree(payload: Path, destination: Path) -> IngestResult:
    result = IngestResult()
    found = 0
    for source in sorted(payload.rglob("*")):
        relative = source.relative_to(payload)
        if source.is_symlink():
            raise BootstrapError(
                f"The supplied material contains a symbolic link that was not imported: {relative}"
            )
        if not source.is_file() or _is_hidden_or_temporary(relative):
            continue
        found += 1
        target = _safe_destination(destination, relative)
        result.add(_copy_source_file(source, target, destination))
    if found == 0:
        raise BootstrapError("No assignment or source files were found at the supplied location.")
    return result


def _extract_zip_safely(archive_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise BootstrapError("The ZIP contains too many entries to import safely.")
            total_size = sum(member.file_size for member in members)
            if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise BootstrapError("The ZIP expands beyond the safe import size limit.")
            for member in members:
                member_path = PurePosixPath(member.filename)
                mode = member.external_attr >> 16
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or stat.S_ISLNK(mode)
                ):
                    raise BootstrapError("The ZIP contains an unsafe path or symbolic link.")
                relative = Path(*member_path.parts)
                target = _safe_destination(destination, relative)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except BootstrapError:
        raise
    except zipfile.BadZipFile as exc:
        raise BootstrapError("The supplied ZIP is damaged or is not a valid ZIP archive.") from exc
    except (RuntimeError, NotImplementedError) as exc:
        raise BootstrapError(
            "The supplied ZIP uses encryption or a compression method that cannot be read safely."
        ) from exc


def ingest_source_path(source_path: Path, workspace: Path) -> IngestResult:
    """Copy a file, folder or safe ZIP into ``workspace/source`` without overwriting."""

    provided = source_path.expanduser()
    if provided.is_symlink():
        raise BootstrapError("A symbolic-link source location cannot be imported safely.")
    supplied = provided.resolve()
    if not supplied.exists():
        raise BootstrapError(f"Codex cannot access the supplied source location: {supplied}")
    destination = workspace.expanduser().resolve() / "source"
    destination.mkdir(parents=True, exist_ok=True)
    if supplied.is_file() and supplied.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="assignment-source-") as temporary:
            extracted = Path(temporary)
            _extract_zip_safely(supplied, extracted)
            return _copy_source_tree(_select_payload_root(extracted), destination)
    if supplied.is_dir():
        return _copy_source_tree(_select_payload_root(supplied), destination)
    if supplied.is_file():
        return _copy_source_file(supplied, destination / supplied.name, destination)
    raise BootstrapError("The supplied source location is not a regular file or folder.")


def read_phase(workspace: Path) -> str:
    state_path = workspace / ".assignment-assistant" / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        return str(payload.get("phase", "UNKNOWN"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError("Codex could not read the assignment's saved progress.") from exc


def start_intake(
    interpreter: Path,
    repository: Path,
    workspace: Path,
    selected_files: Sequence[str],
) -> str:
    phase = read_phase(workspace)
    if phase not in {
        "NEW",
        "SOURCE_INTAKE_REQUIRED",
        "SOURCE_UPDATE_REQUIRED",
        "BRIEFING_REQUIRED",
    }:
        return phase
    if not selected_files:
        raise BootstrapError(
            "The workspace is ready, but the student has not explicitly provided or "
            "identified the assignment materials to use."
        )
    operation = "refresh-sources" if phase == "SOURCE_UPDATE_REQUIRED" else "start"
    command = [str(interpreter), "-m", "assignment_assistant", operation, str(workspace)]
    for selected in selected_files:
        command.extend(("--source", selected))
    _run(
        command,
        "update assignment sources" if operation == "refresh-sources" else "start assignment intake",
        repository,
    )
    return read_phase(workspace)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Internal Codex bootstrap for Academic Assignment Assistant"
    )
    parser.add_argument("--workspace", default="workspace")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="File, folder or ZIP to preserve under the assignment workspace",
    )
    parser.add_argument("--start", action="store_true", help="Start intake after sources exist")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    workspace_arg = Path(args.workspace).expanduser()
    workspace = (
        workspace_arg.resolve()
        if workspace_arg.is_absolute()
        else (repository / workspace_arg).resolve()
    )
    environment = repository / ".venv"
    try:
        interpreter = ensure_environment(repository, environment)
        created = ensure_workspace(interpreter, repository, workspace)
        result = IngestResult()
        for value in args.source:
            result.add(ingest_source_path(Path(value), workspace))
        phase = (
            start_intake(interpreter, repository, workspace, result.selected_files)
            if args.start
            else read_phase(workspace)
        )
    except BootstrapError as exc:
        print("Automatic setup could not finish.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print("The student's supplied source files were not deleted or overwritten.", file=sys.stderr)
        return 2
    except OSError:
        print("Automatic setup could not finish.", file=sys.stderr)
        print(
            "Codex could not read or write one of the required local folders. "
            "Check that the repository and source location are accessible.",
            file=sys.stderr,
        )
        print("The student's supplied source files were not deleted or overwritten.", file=sys.stderr)
        return 2

    print("Automatic setup is ready.")
    print(f"Workspace: {workspace}")
    print(f"Workspace created: {'yes' if created else 'already present'}")
    if args.source:
        print(f"Source files added: {result.copied}")
        print(f"Exact copies skipped: {result.skipped_exact}")
        print(f"Name conflicts preserved: {result.renamed_conflicts}")
    else:
        print("Next: ask the student for assignment files or a source-pack location.")
    print(f"Workflow phase: {phase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
