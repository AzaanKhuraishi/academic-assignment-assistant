"""Built-in and runtime-required capability declarations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .storage import write_json


def default_capabilities() -> Dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "capabilities": {
            "extract.text": {
                "status": "available",
                "provider": "core",
                "limitations": [],
            },
            "extract.office_xml": {
                "status": "available",
                "provider": "core",
                "limitations": ["images", "layout", "equations", "embedded objects"],
            },
            "extract.pdf": {
                "status": "runtime-required",
                "provider": None,
                "limitations": ["core indexes the original but does not read its content"],
            },
            "transcribe.media": {
                "status": "runtime-required",
                "provider": None,
                "limitations": ["transcript must be registered with provenance"],
            },
            "inspect.visual": {
                "status": "runtime-required",
                "provider": None,
                "limitations": ["record completed inspection before final handoff"],
            },
            "research.external": {
                "status": "policy-controlled",
                "provider": None,
                "limitations": ["follow assignment configuration and user authority"],
            },
        },
    }


def write_capability_manifest(workspace: Path) -> Path:
    path = workspace / ".assignment-assistant" / "capabilities.json"
    write_json(path, default_capabilities())
    return path
