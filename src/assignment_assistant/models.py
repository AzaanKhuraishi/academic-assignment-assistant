"""Typed domain models with dependency-free JSON serialisation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AssignmentPhase(str, Enum):
    NEW = "NEW"
    SOURCE_INTAKE_REQUIRED = "SOURCE_INTAKE_REQUIRED"
    SOURCE_FRESHNESS_REQUIRED = "SOURCE_FRESHNESS_REQUIRED"
    SOURCE_UPDATE_REQUIRED = "SOURCE_UPDATE_REQUIRED"
    SOURCE_IMPACT_REQUIRED = "SOURCE_IMPACT_REQUIRED"
    BRIEFING_REQUIRED = "BRIEFING_REQUIRED"
    WAITING_GATE_1 = "WAITING_GATE_1"
    ARCHITECTURE_REQUIRED = "ARCHITECTURE_REQUIRED"
    WAITING_GATE_2 = "WAITING_GATE_2"
    EXECUTION = "EXECUTION"
    FINAL_VALIDATION = "FINAL_VALIDATION"
    REQUIRES_USER_INPUT = "REQUIRES_USER_INPUT"
    READY_FOR_HANDOFF = "READY_FOR_HANDOFF"


class SliceStatus(str, Enum):
    PLANNED = "PLANNED"
    RESEARCHED = "RESEARCHED"
    EVIDENCED = "EVIDENCED"
    ANALYSED = "ANALYSED"
    DRAFTED = "DRAFTED"
    VALIDATED = "VALIDATED"
    USER_REVIEW = "USER_REVIEW"
    ACCEPTED = "ACCEPTED"
    INTEGRATED = "INTEGRATED"


SLICE_SEQUENCE = list(SliceStatus)


@dataclass
class Event:
    timestamp: str
    kind: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Approval:
    gate: str
    approved_at: str
    reviewer: str
    note: str = ""
    artifact: Optional[str] = None


@dataclass
class UserInputRequest:
    request_id: str
    prompt: str
    created_at: str
    status: str = "open"
    response: Optional[str] = None
    resolved_at: Optional[str] = None


@dataclass
class SliceRecord:
    slice_id: str
    title: str
    status: str = SliceStatus.PLANNED.value
    rubric_criteria: List[str] = field(default_factory=list)
    word_budget: Optional[int] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    retry_counts: Dict[str, int] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AssignmentState:
    schema_version: int
    assignment_id: str
    created_at: str
    updated_at: str
    phase: str = AssignmentPhase.SOURCE_INTAKE_REQUIRED.value
    resume_phase: Optional[str] = None
    freshness_resume_phase: Optional[str] = None
    last_substantive_activity_at: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    capability_manifest: Optional[str] = None
    source_manifest: Optional[str] = None
    source_index: Optional[str] = None
    registered_sources: List[str] = field(default_factory=list)
    source_confirmed_at: Optional[str] = None
    source_updates: List[Dict[str, Any]] = field(default_factory=list)
    pending_source_change_report: Optional[str] = None
    routing: Dict[str, Any] = field(default_factory=dict)
    briefing_artifact: Optional[str] = None
    architecture_artifact: Optional[str] = None
    approvals: List[Approval] = field(default_factory=list)
    slices: Dict[str, SliceRecord] = field(default_factory=dict)
    user_inputs: List[UserInputRequest] = field(default_factory=list)
    quality_reports: List[str] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AssignmentState":
        return cls(
            schema_version=max(2, int(raw["schema_version"])),
            assignment_id=str(raw["assignment_id"]),
            created_at=str(raw["created_at"]),
            updated_at=str(raw["updated_at"]),
            phase=str(raw.get("phase", AssignmentPhase.NEW.value)),
            resume_phase=raw.get("resume_phase"),
            freshness_resume_phase=raw.get("freshness_resume_phase"),
            last_substantive_activity_at=raw.get(
                "last_substantive_activity_at", raw.get("updated_at")
            ),
            config=dict(raw.get("config", {})),
            capability_manifest=raw.get("capability_manifest"),
            source_manifest=raw.get("source_manifest"),
            source_index=raw.get("source_index"),
            registered_sources=list(raw.get("registered_sources", [])),
            source_confirmed_at=raw.get("source_confirmed_at"),
            source_updates=list(raw.get("source_updates", [])),
            pending_source_change_report=raw.get("pending_source_change_report"),
            routing=dict(raw.get("routing", {})),
            briefing_artifact=raw.get("briefing_artifact"),
            architecture_artifact=raw.get("architecture_artifact"),
            approvals=[Approval(**item) for item in raw.get("approvals", [])],
            slices={
                key: SliceRecord(**value)
                for key, value in raw.get("slices", {}).items()
            },
            user_inputs=[
                UserInputRequest(**item) for item in raw.get("user_inputs", [])
            ],
            quality_reports=list(raw.get("quality_reports", [])),
            events=[Event(**item) for item in raw.get("events", [])],
        )
