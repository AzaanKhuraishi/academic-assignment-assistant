"""Deterministic checks that complement, but do not replace, scholarly review."""

from __future__ import annotations

import re
from pathlib import Path
import json
from typing import Dict, List

from .models import AssignmentState, SliceStatus


PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBC\b", re.IGNORECASE),
    re.compile(r"\[EVIDENCE GAP\]", re.IGNORECASE),
    re.compile(r"\[ASSUMPTION\]", re.IGNORECASE),
    re.compile(r"\[USER EXPERIENCE\]", re.IGNORECASE),
)


def validate_text_artifact(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: List[Dict[str, object]] = []
    for pattern in PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                {
                    "severity": "blocker",
                    "kind": "unresolved_marker",
                    "line": line,
                    "match": match.group(0),
                }
            )
    return {
        "path": str(path),
        "word_count": len(re.findall(r"\b\w+(?:[-’']\w+)*\b", text)),
        "findings": findings,
        "passed": not findings,
    }


def validate_state_for_final(state: AssignmentState) -> Dict[str, object]:
    findings: List[Dict[str, str]] = []
    if not state.briefing_artifact:
        findings.append({"severity": "blocker", "message": "Missing Gate 1 briefing"})
    if not state.architecture_artifact:
        findings.append({"severity": "blocker", "message": "Missing Gate 2 architecture"})
    gates = {approval.gate for approval in state.approvals}
    for gate in ("gate1", "gate2"):
        if gate not in gates:
            findings.append({"severity": "blocker", "message": f"Missing {gate} approval"})
    for slice_id, record in state.slices.items():
        if record.status != SliceStatus.INTEGRATED.value:
            findings.append(
                {"severity": "blocker", "message": f"Slice {slice_id} is {record.status}"}
            )
    for request in state.user_inputs:
        if request.status == "open":
            findings.append(
                {"severity": "blocker", "message": f"Open user input: {request.prompt}"}
            )
    return {"passed": not findings, "findings": findings}


def validate_workspace_for_final(workspace: Path, state: AssignmentState) -> Dict[str, object]:
    report = validate_state_for_final(state)
    findings = list(report["findings"])
    final_dir = workspace / "assignment" / "final"
    deliverables = sorted(
        path
        for path in final_dir.glob("*")
        if path.is_file()
        and path.name not in {"quality-report.json", "visual-inspection.json"}
        and not path.name.startswith(".")
    )
    artifact_reports: List[Dict[str, object]] = []
    if not deliverables:
        findings.append({"severity": "blocker", "message": "No final deliverable found"})

    for path in deliverables:
        if path.suffix.lower() in {".md", ".txt"}:
            artifact_report = validate_text_artifact(path)
            artifact_reports.append(artifact_report)
            for finding in artifact_report["findings"]:
                findings.append(
                    {
                        "severity": "blocker",
                        "message": f"{path.name}:{finding['line']} contains {finding['match']}",
                    }
                )

    layout_files = [
        path for path in deliverables if path.suffix.lower() in {".pdf", ".docx", ".pptx"}
    ]
    visual_record = final_dir / "visual-inspection.json"
    if layout_files:
        if not visual_record.exists():
            findings.append(
                {
                    "severity": "blocker",
                    "message": "Layout-dependent output requires assignment/final/visual-inspection.json",
                }
            )
        else:
            try:
                visual = json.loads(visual_record.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                visual = {}
            inspected = set(visual.get("inspected_files", []))
            missing = [
                path.relative_to(workspace).as_posix()
                for path in layout_files
                if path.relative_to(workspace).as_posix() not in inspected
            ]
            if not visual.get("passed") or missing:
                findings.append(
                    {
                        "severity": "blocker",
                        "message": "Visual inspection is incomplete for: " + ", ".join(missing or ["recorded files"]),
                    }
                )

    return {
        "passed": not findings,
        "findings": findings,
        "deliverables": [path.relative_to(workspace).as_posix() for path in deliverables],
        "artifact_reports": artifact_reports,
    }
