"""Workspace paths and atomic state persistence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from .models import AssignmentState


CONTROL_DIR = ".assignment-assistant"


class WorkspaceError(RuntimeError):
    pass


def resolve_workspace(path: Path) -> Path:
    return path.expanduser().resolve()


def ensure_within_workspace(workspace: Path, candidate: Path) -> Path:
    resolved_workspace = resolve_workspace(workspace)
    resolved_candidate = candidate.expanduser().resolve()
    try:
        resolved_candidate.relative_to(resolved_workspace)
    except ValueError as exc:
        raise WorkspaceError(
            f"Artifact must be inside workspace: {resolved_candidate}"
        ) from exc
    return resolved_candidate


def control_path(workspace: Path) -> Path:
    return workspace / CONTROL_DIR


def state_path(workspace: Path) -> Path:
    return control_path(workspace) / "state.json"


def load_state(workspace: Path) -> AssignmentState:
    path = state_path(workspace)
    if not path.exists():
        raise WorkspaceError(
            f"No assignment state at {path}. Run 'assignment-assistant init' first."
        )
    return AssignmentState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(workspace: Path, state: AssignmentState) -> None:
    directory = control_path(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="state-", suffix=".json", dir=str(directory)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, state_path(workspace))
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
