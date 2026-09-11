"""Create an assignment workspace without touching supplied source files."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .capabilities import write_capability_manifest
from .configuration import DEFAULT_CONFIG, render_default_config
from .models import AssignmentPhase, AssignmentState, Event
from .storage import CONTROL_DIR, WorkspaceError, save_state


WORKSPACE_DIRECTORIES = (
    "source",
    "derived/reading",
    "derived/transcripts",
    "assignment/briefing",
    "assignment/research",
    "assignment/working",
    "assignment/final",
    f"{CONTROL_DIR}/tasks",
)

BRIEFING_TEMPLATE = """# Assessment briefing

## 1. Task in plain English

## 2. Required deliverables and formats

## 3. Assessment purpose

## 4. Learning outcomes and marking criteria

## 5. Word-count and structural constraints

## 6. Mandatory concepts, methods, evidence and appendices

## 7. Role of the case, client, dataset or personal experience

## 8. Citation and research expectations

## 9. Ambiguities, conflicts, risks and evidence gaps

## 10. Proposed interpretation and decisions required
"""

ARCHITECTURE_TEMPLATE = """# Assignment architecture

## Central argument

## Rubric and learning-outcome map

| Section or slice | Purpose | Word budget | Criteria | Evidence | User dependency |
|---|---|---:|---|---|---|

## Planned figures, tables and appendices

## Vertical slices and dependencies

## Material trade-offs for Gate 2
"""

VISUAL_INSPECTION_TEMPLATE = """{
  "passed": false,
  "inspected_at": null,
  "inspected_files": [],
  "notes": "Render each PDF, DOCX or PPTX and record the completed visual review."
}
"""

EVIDENCE_MATRIX_TEMPLATE = """# Evidence matrix

| Slice | Claim | Source | Evidence or finding | Strength | Limitation | Citation status |
|---|---|---|---|---|---|---|
"""

RESEARCH_LOG_TEMPLATE = """# Research log

| Date | Slice | Question or query | Sources checked | Decision and reason |
|---|---|---|---|---|
"""

SLICE_TEMPLATE = """# Vertical slice

## Purpose, rubric criteria and word budget

## Research questions

## Evidence bundle

## Claim–evidence–reasoning chain

## Draft contribution

## Limitations, alternatives and dependencies

## Validation and user feedback

## Integration record
"""

USER_INPUT_TEMPLATE = """# Authentic user input

Use this artefact only for facts, views, judgements or experiences that the user can
verify. Preserve the appropriate label: `[USER FACT]`, `[USER VIEW]`,
`[USER EXPERIENCE]`, `[ASSUMPTION]` or `[EVIDENCE GAP]`.

## Exact question asked

## User's response

## How the response may be used

## Confirmation status
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def initialise_workspace(workspace: Path) -> AssignmentState:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    state_file = workspace / CONTROL_DIR / "state.json"
    if state_file.exists():
        raise WorkspaceError(f"Workspace is already initialised: {workspace}")

    for relative in WORKSPACE_DIRECTORIES:
        (workspace / relative).mkdir(parents=True, exist_ok=True)

    config_path = workspace / "assignment-assistant.yaml"
    if not config_path.exists():
        config_path.write_text(render_default_config(), encoding="utf-8")

    template_dir = workspace / CONTROL_DIR / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "assessment-briefing.md").write_text(
        BRIEFING_TEMPLATE, encoding="utf-8"
    )
    (template_dir / "assignment-architecture.md").write_text(
        ARCHITECTURE_TEMPLATE, encoding="utf-8"
    )
    (template_dir / "visual-inspection.json").write_text(
        VISUAL_INSPECTION_TEMPLATE, encoding="utf-8"
    )
    (template_dir / "evidence-matrix.md").write_text(
        EVIDENCE_MATRIX_TEMPLATE, encoding="utf-8"
    )
    (template_dir / "research-log.md").write_text(
        RESEARCH_LOG_TEMPLATE, encoding="utf-8"
    )
    (template_dir / "vertical-slice.md").write_text(
        SLICE_TEMPLATE, encoding="utf-8"
    )
    (template_dir / "authentic-user-input.md").write_text(
        USER_INPUT_TEMPLATE, encoding="utf-8"
    )

    now = utc_now()
    capability_path = write_capability_manifest(workspace)
    state = AssignmentState(
        schema_version=2,
        assignment_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        phase=AssignmentPhase.SOURCE_INTAKE_REQUIRED.value,
        last_substantive_activity_at=now,
        config=dict(DEFAULT_CONFIG),
        capability_manifest=capability_path.relative_to(workspace).as_posix(),
        events=[Event(now, "workspace.initialised", "Workspace initialised")],
    )
    save_state(workspace, state)
    return state
