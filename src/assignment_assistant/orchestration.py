"""Deterministic assignment and vertical-slice state machine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    Approval,
    AssignmentPhase,
    AssignmentState,
    Event,
    SLICE_SEQUENCE,
    SliceRecord,
    SliceStatus,
    UserInputRequest,
)
from .storage import WorkspaceError, ensure_within_workspace


FAILURE_ROUTES: Dict[str, SliceStatus] = {
    "citation_problem": SliceStatus.EVIDENCED,
    "missing_research": SliceStatus.RESEARCHED,
    "weak_argument": SliceStatus.ANALYSED,
    "wrong_premise": SliceStatus.PLANNED,
    "writing_problem": SliceStatus.DRAFTED,
    "rubric_misalignment": SliceStatus.ANALYSED,
}


class TransitionError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _event(
    state: AssignmentState,
    kind: str,
    message: str,
    *,
    substantive: bool = True,
    **data: object,
) -> None:
    state.updated_at = utc_now()
    if substantive:
        state.last_substantive_activity_at = state.updated_at
    state.events.append(Event(state.updated_at, kind, message, data))


def record_intake(
    state: AssignmentState,
    config: Dict[str, object],
    manifest_path: str,
    index_path: str,
    routing: Dict[str, object],
    registered_sources: Optional[List[str]] = None,
) -> None:
    if state.phase not in {
        AssignmentPhase.NEW.value,
        AssignmentPhase.SOURCE_INTAKE_REQUIRED.value,
        AssignmentPhase.BRIEFING_REQUIRED.value,
    }:
        raise TransitionError(f"Cannot run intake while phase is {state.phase}")
    selected = sorted(set(registered_sources or []))
    if not selected:
        raise TransitionError(
            "Source intake requires files explicitly provided or identified by the user"
        )
    state.config = dict(config)
    state.source_manifest = manifest_path
    state.source_index = index_path
    state.registered_sources = selected
    state.source_confirmed_at = utc_now()
    state.routing = dict(routing)
    state.phase = AssignmentPhase.BRIEFING_REQUIRED.value
    _event(
        state,
        "intake.completed",
        "Explicitly selected source intake completed",
        routing=routing,
        registered_source_count=len(selected),
    )


def require_source_intake_if_unconfirmed(state: AssignmentState) -> bool:
    """Move legacy or incomplete state behind the explicit initial source gate."""

    if state.registered_sources or state.phase in {
        AssignmentPhase.NEW.value,
        AssignmentPhase.SOURCE_INTAKE_REQUIRED.value,
    }:
        return False
    state.phase = AssignmentPhase.SOURCE_INTAKE_REQUIRED.value
    _event(
        state,
        "source_intake.required",
        "Explicit assignment source selection required",
        substantive=False,
    )
    return True


def require_source_freshness_if_due(
    state: AssignmentState,
    threshold_hours: int = 6,
    now: Optional[datetime] = None,
) -> bool:
    """Pause a resumed assignment when its last substantive activity is stale."""

    if not state.registered_sources or state.phase in {
        AssignmentPhase.NEW.value,
        AssignmentPhase.SOURCE_INTAKE_REQUIRED.value,
        AssignmentPhase.SOURCE_FRESHNESS_REQUIRED.value,
        AssignmentPhase.SOURCE_UPDATE_REQUIRED.value,
        AssignmentPhase.SOURCE_IMPACT_REQUIRED.value,
        AssignmentPhase.READY_FOR_HANDOFF.value,
    }:
        return False
    reference_text = state.last_substantive_activity_at or state.updated_at
    try:
        reference = datetime.fromisoformat(reference_text)
    except ValueError as exc:
        raise TransitionError("Saved activity timestamp is invalid") from exc
    current = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if current - reference < timedelta(hours=threshold_hours):
        return False
    state.freshness_resume_phase = state.phase
    state.phase = AssignmentPhase.SOURCE_FRESHNESS_REQUIRED.value
    _event(
        state,
        "source_freshness.required",
        "Source freshness confirmation required after inactivity",
        substantive=False,
        threshold_hours=threshold_hours,
        inactive_since=reference.isoformat(),
    )
    return True


def record_source_freshness_answer(state: AssignmentState, has_updates: bool) -> None:
    if state.phase != AssignmentPhase.SOURCE_FRESHNESS_REQUIRED.value:
        raise TransitionError(
            f"Source freshness cannot be answered while phase is {state.phase}"
        )
    if has_updates:
        state.phase = AssignmentPhase.SOURCE_UPDATE_REQUIRED.value
        _event(
            state,
            "source_freshness.updated",
            "User reported new or updated assignment material",
        )
        return
    state.phase = state.freshness_resume_phase or AssignmentPhase.BRIEFING_REQUIRED.value
    state.freshness_resume_phase = None
    _event(
        state,
        "source_freshness.current",
        "User confirmed that no new or updated assignment material is available",
    )


def record_source_update(
    state: AssignmentState,
    manifest_path: str,
    index_path: str,
    routing: Dict[str, object],
    registered_sources: List[str],
    change_report: str,
    changes: Dict[str, object],
) -> None:
    if state.phase != AssignmentPhase.SOURCE_UPDATE_REQUIRED.value:
        raise TransitionError(f"Cannot update sources while phase is {state.phase}")
    state.source_manifest = manifest_path
    state.source_index = index_path
    state.routing = dict(routing)
    state.registered_sources = sorted(set(registered_sources))
    state.source_confirmed_at = utc_now()
    state.pending_source_change_report = change_report
    state.source_updates.append(
        {
            "recorded_at": utc_now(),
            "change_report": change_report,
            "changes": dict(changes),
            "impact": None,
            "impact_artifact": None,
        }
    )
    state.phase = AssignmentPhase.SOURCE_IMPACT_REQUIRED.value
    _event(
        state,
        "source_update.completed",
        "Incremental source intake completed; impact assessment required",
        change_report=change_report,
        changes=changes,
    )


def resolve_source_impact(
    state: AssignmentState,
    workspace: Path,
    artifact: Path,
    impact: str,
) -> None:
    if state.phase != AssignmentPhase.SOURCE_IMPACT_REQUIRED.value:
        raise TransitionError(f"Source impact cannot be resolved while phase is {state.phase}")
    checked = ensure_within_workspace(workspace, artifact)
    if not checked.is_file():
        raise WorkspaceError(f"Source impact artifact does not exist: {checked}")
    if impact not in {"none", "briefing", "architecture", "slices"}:
        raise TransitionError("Source impact must be none, briefing, architecture, or slices")
    relative = checked.relative_to(workspace.resolve()).as_posix()
    update = state.source_updates[-1]
    update["impact"] = impact
    update["impact_artifact"] = relative
    update["resolved_at"] = utc_now()
    if impact == "briefing":
        state.briefing_artifact = None
        state.architecture_artifact = None
        state.phase = AssignmentPhase.BRIEFING_REQUIRED.value
    elif impact == "architecture":
        state.architecture_artifact = None
        gate_1_approved = any(item.gate == "gate1" for item in state.approvals)
        state.phase = (
            AssignmentPhase.ARCHITECTURE_REQUIRED.value
            if gate_1_approved
            else AssignmentPhase.BRIEFING_REQUIRED.value
        )
    else:
        state.phase = state.freshness_resume_phase or AssignmentPhase.BRIEFING_REQUIRED.value
    state.freshness_resume_phase = None
    state.pending_source_change_report = None
    _event(
        state,
        "source_impact.resolved",
        f"Source update impact recorded as {impact}",
        impact=impact,
        artifact=relative,
    )


def confirm_discipline(state: AssignmentState, discipline: str) -> None:
    if state.phase != AssignmentPhase.BRIEFING_REQUIRED.value:
        raise TransitionError(
            f"Discipline can only be confirmed before Gate 1, not during {state.phase}"
        )
    discipline = discipline.lower()
    state.config["discipline"] = discipline
    prior_scores = dict(state.routing.get("scores", {}))
    state.routing = {
        "discipline": discipline,
        "confidence": 1.0,
        "requires_confirmation": False,
        "reason": "Explicit user confirmation",
        "scores": prior_scores,
        "matched_terms": state.routing.get("matched_terms", {}),
    }
    _event(
        state,
        "discipline.confirmed",
        f"Discipline confirmed as {discipline}",
        discipline=discipline,
    )


def submit_briefing(state: AssignmentState, workspace: Path, artifact: Path) -> None:
    if state.phase != AssignmentPhase.BRIEFING_REQUIRED.value:
        raise TransitionError(f"Briefing cannot be submitted while phase is {state.phase}")
    checked = ensure_within_workspace(workspace, artifact)
    if not checked.is_file():
        raise WorkspaceError(f"Briefing artifact does not exist: {checked}")
    state.briefing_artifact = checked.relative_to(workspace.resolve()).as_posix()
    state.phase = AssignmentPhase.WAITING_GATE_1.value
    _event(state, "briefing.submitted", "Assessment briefing submitted for Gate 1")


def submit_architecture(state: AssignmentState, workspace: Path, artifact: Path) -> None:
    if state.phase != AssignmentPhase.ARCHITECTURE_REQUIRED.value:
        raise TransitionError(f"Architecture cannot be submitted while phase is {state.phase}")
    checked = ensure_within_workspace(workspace, artifact)
    if not checked.is_file():
        raise WorkspaceError(f"Architecture artifact does not exist: {checked}")
    state.architecture_artifact = checked.relative_to(workspace.resolve()).as_posix()
    state.phase = AssignmentPhase.WAITING_GATE_2.value
    _event(state, "architecture.submitted", "Assignment architecture submitted for Gate 2")


def approve_gate(
    state: AssignmentState,
    gate: str,
    reviewer: str,
    note: str = "",
) -> None:
    gate = gate.lower().replace("_", "")
    if gate in {"1", "gate1"}:
        expected = AssignmentPhase.WAITING_GATE_1.value
        next_phase = AssignmentPhase.ARCHITECTURE_REQUIRED.value
        artifact = state.briefing_artifact
        canonical_gate = "gate1"
    elif gate in {"2", "gate2"}:
        expected = AssignmentPhase.WAITING_GATE_2.value
        next_phase = AssignmentPhase.EXECUTION.value
        artifact = state.architecture_artifact
        canonical_gate = "gate2"
    else:
        raise TransitionError("Gate must be gate1 or gate2")
    if state.phase != expected:
        raise TransitionError(f"{canonical_gate} cannot be approved while phase is {state.phase}")
    now = utc_now()
    state.approvals.append(Approval(canonical_gate, now, reviewer, note, artifact))
    state.phase = next_phase
    _event(state, "gate.approved", f"{canonical_gate} approved", reviewer=reviewer)


def add_slice(
    state: AssignmentState,
    slice_id: str,
    title: str,
    rubric_criteria: Optional[list] = None,
    word_budget: Optional[int] = None,
) -> None:
    if state.phase != AssignmentPhase.EXECUTION.value:
        raise TransitionError(f"Slices can only be added during EXECUTION, not {state.phase}")
    if not slice_id or slice_id in state.slices:
        raise TransitionError(f"Slice identifier is empty or already exists: {slice_id!r}")
    if word_budget is not None and word_budget < 0:
        raise TransitionError("word_budget must be non-negative")
    record = SliceRecord(
        slice_id=slice_id,
        title=title,
        rubric_criteria=list(rubric_criteria or []),
        word_budget=word_budget,
    )
    record.history.append({"timestamp": utc_now(), "status": record.status, "reason": "created"})
    state.slices[slice_id] = record
    _event(state, "slice.created", f"Slice {slice_id} created", title=title)


def advance_slice(
    state: AssignmentState,
    workspace: Path,
    slice_id: str,
    target: str,
    artifact: Optional[Path] = None,
) -> None:
    if state.phase != AssignmentPhase.EXECUTION.value:
        raise TransitionError(f"Slices can only advance during EXECUTION, not {state.phase}")
    if slice_id not in state.slices:
        raise TransitionError(f"Unknown slice: {slice_id}")
    record = state.slices[slice_id]
    current_status = SliceStatus(record.status)
    try:
        target_status = SliceStatus(target.upper())
    except ValueError as exc:
        raise TransitionError(f"Unknown slice status: {target}") from exc
    current_index = SLICE_SEQUENCE.index(current_status)
    if target_status == SliceStatus.ACCEPTED:
        raise TransitionError("Use slice-accept to record the user's acceptance")
    if current_index + 1 >= len(SLICE_SEQUENCE) or SLICE_SEQUENCE[current_index + 1] != target_status:
        expected = (
            SLICE_SEQUENCE[current_index + 1].value
            if current_index + 1 < len(SLICE_SEQUENCE)
            else "none"
        )
        raise TransitionError(
            f"Invalid transition {current_status.value} -> {target_status.value}; expected {expected}"
        )
    artifact_required = target_status in {
        SliceStatus.RESEARCHED,
        SliceStatus.EVIDENCED,
        SliceStatus.ANALYSED,
        SliceStatus.DRAFTED,
        SliceStatus.VALIDATED,
        SliceStatus.INTEGRATED,
    }
    if artifact_required and artifact is None:
        raise TransitionError(f"An artifact is required when advancing to {target_status.value}")
    if artifact is not None:
        checked = ensure_within_workspace(workspace, artifact)
        if not checked.is_file():
            raise WorkspaceError(f"Slice artifact does not exist: {checked}")
        record.artifacts[target_status.value] = checked.relative_to(workspace.resolve()).as_posix()
    record.status = target_status.value
    record.history.append(
        {"timestamp": utc_now(), "status": record.status, "reason": "advanced"}
    )
    _event(
        state,
        "slice.advanced",
        f"Slice {slice_id} advanced to {target_status.value}",
    )


def accept_slice(
    state: AssignmentState,
    slice_id: str,
    reviewer: str,
    note: str = "",
) -> None:
    if state.phase != AssignmentPhase.EXECUTION.value:
        raise TransitionError(f"Slices can only be accepted during EXECUTION, not {state.phase}")
    if slice_id not in state.slices:
        raise TransitionError(f"Unknown slice: {slice_id}")
    record = state.slices[slice_id]
    if record.status != SliceStatus.USER_REVIEW.value:
        raise TransitionError(
            f"Slice {slice_id} cannot be accepted while status is {record.status}"
        )
    if not reviewer.strip():
        raise TransitionError("A reviewer is required")
    record.status = SliceStatus.ACCEPTED.value
    record.history.append(
        {
            "timestamp": utc_now(),
            "status": SliceStatus.ACCEPTED.value,
            "reason": "accepted",
            "reviewer": reviewer,
            "note": note,
        }
    )
    _event(
        state,
        "slice.accepted",
        f"Slice {slice_id} accepted by {reviewer}",
        reviewer=reviewer,
    )


def reject_slice(
    state: AssignmentState,
    slice_id: str,
    failure: str,
    reason: str,
    origin: str = "internal",
) -> None:
    if state.phase != AssignmentPhase.EXECUTION.value:
        raise TransitionError(f"Slices can only be rejected during EXECUTION, not {state.phase}")
    if slice_id not in state.slices:
        raise TransitionError(f"Unknown slice: {slice_id}")
    if failure not in FAILURE_ROUTES:
        raise TransitionError(
            "Unknown failure type. Choose: " + ", ".join(sorted(FAILURE_ROUTES))
        )
    record = state.slices[slice_id]
    target = FAILURE_ROUTES[failure]
    if SLICE_SEQUENCE.index(target) > SLICE_SEQUENCE.index(SliceStatus(record.status)):
        raise TransitionError(
            f"Failure route {failure} would move slice {slice_id} forward from "
            f"{record.status} to {target.value}"
        )
    retry_count = record.retry_counts.get(failure, 0) + 1
    record.retry_counts[failure] = retry_count
    record.status = target.value
    record.history.append(
        {
            "timestamp": utc_now(),
            "status": target.value,
            "reason": "rejected",
            "failure": failure,
            "feedback": reason,
            "origin": origin,
            "retry": retry_count,
        }
    )
    _event(
        state,
        "slice.rejected",
        f"Slice {slice_id} routed to {target.value}",
        failure=failure,
        origin=origin,
        retry=retry_count,
    )
    maximum = int(state.config.get("max_autonomous_retries", 3))
    if origin == "internal" and retry_count > maximum:
        require_user_input(
            state,
            f"Slice {slice_id} exceeded {maximum} autonomous retries for {failure}. "
            f"Latest feedback: {reason}",
        )


def require_user_input(state: AssignmentState, prompt: str) -> UserInputRequest:
    if state.phase != AssignmentPhase.REQUIRES_USER_INPUT.value:
        state.resume_phase = state.phase
    request = UserInputRequest(str(uuid.uuid4()), prompt, utc_now())
    state.user_inputs.append(request)
    state.phase = AssignmentPhase.REQUIRES_USER_INPUT.value
    _event(state, "user_input.required", "Workflow paused for authentic user input", request_id=request.request_id)
    return request


def resolve_user_input(state: AssignmentState, request_id: str, response: str) -> None:
    request = next((item for item in state.user_inputs if item.request_id == request_id), None)
    if request is None or request.status != "open":
        raise TransitionError(f"No open user-input request: {request_id}")
    if not response.strip():
        raise TransitionError("A non-empty response is required")
    request.status = "resolved"
    request.response = response
    request.resolved_at = utc_now()
    if not any(item.status == "open" for item in state.user_inputs):
        state.phase = state.resume_phase or AssignmentPhase.EXECUTION.value
        state.resume_phase = None
    _event(state, "user_input.resolved", "User input recorded", request_id=request_id)


def begin_final_validation(state: AssignmentState) -> None:
    if state.phase != AssignmentPhase.EXECUTION.value:
        raise TransitionError(f"Final validation cannot begin while phase is {state.phase}")
    if not state.slices:
        raise TransitionError("At least one slice is required")
    incomplete = [key for key, value in state.slices.items() if value.status != SliceStatus.INTEGRATED.value]
    if incomplete:
        raise TransitionError("Slices are not integrated: " + ", ".join(incomplete))
    state.phase = AssignmentPhase.FINAL_VALIDATION.value
    _event(state, "validation.started", "Whole-assignment final validation started")


def mark_ready_for_handoff(state: AssignmentState, report: str) -> None:
    if state.phase != AssignmentPhase.FINAL_VALIDATION.value:
        raise TransitionError(f"Cannot mark ready while phase is {state.phase}")
    if any(item.status == "open" for item in state.user_inputs):
        raise TransitionError("Open user-input requests must be resolved")
    state.quality_reports.append(report)
    state.phase = AssignmentPhase.READY_FOR_HANDOFF.value
    _event(state, "handoff.ready", "Assignment package is ready for user handoff")
