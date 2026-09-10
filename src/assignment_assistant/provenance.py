"""Register runtime-generated reading copies, transcripts and other derivations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .intake import sha256_file
from .storage import WorkspaceError, ensure_within_workspace, write_json


def register_derivation(
    workspace: Path,
    source: Path,
    derived: Path,
    method: str,
    verification_status: str = "unchecked",
) -> Dict[str, str]:
    workspace = workspace.resolve()
    checked_source = ensure_within_workspace(workspace, source)
    checked_derived = ensure_within_workspace(workspace, derived)
    if not checked_source.is_file() or not checked_derived.is_file():
        raise WorkspaceError("Source and derived paths must both be existing files")
    try:
        checked_source.relative_to((workspace / "source").resolve())
    except ValueError as exc:
        raise WorkspaceError("Registered source must be inside workspace/source") from exc
    try:
        checked_derived.relative_to((workspace / "derived").resolve())
    except ValueError as exc:
        raise WorkspaceError("Registered derivation must be inside workspace/derived") from exc
    if not method.strip():
        raise WorkspaceError("A derivation method is required")
    if verification_status not in {"unchecked", "checked"}:
        raise WorkspaceError("verification_status must be unchecked or checked")

    record = {
        "source": checked_source.relative_to(workspace).as_posix(),
        "source_sha256": sha256_file(checked_source),
        "derived": checked_derived.relative_to(workspace).as_posix(),
        "derived_sha256": sha256_file(checked_derived),
        "method": method,
        "verification_status": verification_status,
        "registered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    path = workspace / "assignment" / "research" / "derivation-provenance.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkspaceError(f"Invalid provenance file: {path}") from exc
    else:
        payload = {"records": []}
    records = list(payload.get("records", []))
    existing = next(
        (
            item
            for item in records
            if item.get("source_sha256") == record["source_sha256"]
            and item.get("derived_sha256") == record["derived_sha256"]
        ),
        None,
    )
    if existing is None:
        records.append(record)
    payload["records"] = records
    write_json(path, payload)
    return existing or record
