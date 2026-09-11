"""Codex task-packet renderer.

The adapter deliberately does not call a hosted API. Codex reads the repository's
AGENTS.md, executes the packet in the user's existing environment, and records the
result through the CLI state machine.
"""

from __future__ import annotations

from pathlib import Path

from ..bootstrap import virtualenv_python
from ..models import AssignmentPhase, AssignmentState, SliceStatus


class CodexAdapter:
    name = "codex"

    def render_next_task(self, workspace: Path, state: AssignmentState) -> str:
        phase = AssignmentPhase(state.phase)
        contract = "agents/contracts/orchestrator.md"
        next_command = ""
        repository = Path(__file__).resolve().parents[3]
        interpreter = virtualenv_python(repository / ".venv")
        engine = f'"{interpreter}" -m assignment_assistant'
        quoted_workspace = f'"{workspace}"'
        common = (
            "Use UK English. Do not invent facts, citations, quotations, page numbers, "
            "or personal experience. Read SOURCE_INDEX.md before opening sources. "
            "Operate the CLI and state machine yourself. Do not ask the user to run "
            "commands or interpret internal state; report the outcome and next human "
            "decision in plain language.\n"
        )
        if phase == AssignmentPhase.NEW:
            action = (
                "Check whether source/ contains assignment material. If it is empty, ask "
                "the user to attach files or provide an accessible file, ZIP or folder "
                "location. Preserve supplied originals, then run source intake before "
                "interpreting the assignment."
            )
            contract = "agents/contracts/intake.md"
            next_command = f"{engine} start {quoted_workspace}"
        elif phase == AssignmentPhase.BRIEFING_REQUIRED:
            if state.routing.get("requires_confirmation"):
                contract = "agents/contracts/subject-router.md"
                suggestion = state.routing.get("discipline", "generic")
                action = (
                    f"Stop and ask the user to confirm the suggested discipline {suggestion!r}. "
                    "Explain the recorded scores and mixed or weak evidence."
                )
                next_command = (
                    f"{engine} confirm-discipline {quoted_workspace} <discipline>"
                )
            else:
                contract = "agents/contracts/brief-interpreter.md"
                action = (
                    "Read the governing sources and produce "
                    "assignment/briefing/ASSESSMENT_BRIEFING.md using "
                    ".assignment-assistant/templates/assessment-briefing.md. "
                    "Then register it with the submit-briefing command and stop for Gate 1."
                )
                next_command = (
                    f"{engine} submit-briefing {quoted_workspace} "
                    "assignment/briefing/ASSESSMENT_BRIEFING.md"
                )
        elif phase == AssignmentPhase.WAITING_GATE_1:
            action = "Stop. The user must approve or amend the assessment interpretation."
        elif phase == AssignmentPhase.ARCHITECTURE_REQUIRED:
            contract = "agents/contracts/architect.md"
            action = (
                "Build assignment/working/ASSIGNMENT_ARCHITECTURE.md from the approved briefing "
                "and .assignment-assistant/templates/assignment-architecture.md. "
                "Map every section to the rubric and word budget, register it, and stop for Gate 2."
            )
            next_command = (
                f"{engine} submit-architecture {quoted_workspace} "
                "assignment/working/ASSIGNMENT_ARCHITECTURE.md"
            )
        elif phase == AssignmentPhase.WAITING_GATE_2:
            action = "Stop. The user must approve or amend the assignment architecture."
        elif phase == AssignmentPhase.EXECUTION:
            pending = [
                record for record in state.slices.values() if record.status != SliceStatus.INTEGRATED.value
            ]
            if pending:
                record = pending[0]
                contract = self._slice_contract(record.status)
                action = (
                    f"Work on slice {record.slice_id!r} ({record.title}) at state {record.status}. "
                    "Complete only the evidence, analysis, drafting or validation work needed for "
                    "its next valid transition, then record the artifact and transition."
                )
            else:
                contract = "agents/contracts/architect.md"
                action = "Define slices from the approved architecture, or begin final validation if all are integrated."
        elif phase == AssignmentPhase.REQUIRES_USER_INPUT:
            open_items = [item.prompt for item in state.user_inputs if item.status == "open"]
            action = "Stop and ask the user for: " + "; ".join(open_items)
        elif phase == AssignmentPhase.FINAL_VALIDATION:
            contract = "agents/contracts/evidence-validator.md"
            action = (
                "Run the whole-assignment quality gate: compliance, argument, evidence, "
                "references, authenticity, word count, and rendered-document inspection."
            )
        else:
            contract = "agents/contracts/integrator.md"
            action = "Present the deliverables and compliance summary. Submission remains the user's action."
        discipline = str(state.routing.get("discipline", "generic"))
        overlay = f"overlays/{discipline}.md"
        return (
            "# Codex task packet\n\n"
            f"- Workspace: `{workspace}`\n"
            f"- Assignment ID: `{state.assignment_id}`\n"
            f"- Phase: `{state.phase}`\n"
            f"- Routed discipline: `{state.routing.get('discipline', 'not yet routed')}`\n"
            f"- Discipline overlay: `{overlay}`\n"
            f"- Active contract: `{contract}`\n"
            f"- Capability manifest: `{state.capability_manifest or 'not recorded'}`\n"
            f"- External research policy: `{state.config.get('external_research', 'ask')}`\n\n"
            "## Governing rules\n\n"
            f"{common}\n"
            "## Next action\n\n"
            f"{action}\n"
            + (f"\n## Record the result\n\n`{next_command}`\n" if next_command else "")
        )

    @staticmethod
    def _slice_contract(status: str) -> str:
        return {
            SliceStatus.PLANNED.value: "agents/contracts/researcher.md",
            SliceStatus.RESEARCHED.value: "agents/contracts/researcher.md",
            SliceStatus.EVIDENCED.value: "agents/contracts/slice-builder.md",
            SliceStatus.ANALYSED.value: "agents/contracts/slice-builder.md",
            SliceStatus.DRAFTED.value: "agents/contracts/evidence-validator.md",
            SliceStatus.VALIDATED.value: "agents/contracts/rubric-critic.md",
            SliceStatus.USER_REVIEW.value: "agents/contracts/orchestrator.md",
            SliceStatus.ACCEPTED.value: "agents/contracts/integrator.md",
            SliceStatus.INTEGRATED.value: "agents/contracts/integrator.md",
        }[status]
