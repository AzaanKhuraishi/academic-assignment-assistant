"""Runtime adapter protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import AssignmentState


class RuntimeAdapter(Protocol):
    name: str

    def render_next_task(self, workspace: Path, state: AssignmentState) -> str:
        """Return a human-readable task packet for the active runtime."""
