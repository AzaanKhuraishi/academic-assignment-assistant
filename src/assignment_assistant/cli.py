"""Command-line interface for the transparent workflow engine."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from .adapters.codex import CodexAdapter
from .capabilities import write_capability_manifest
from .configuration import ALLOWED_DISCIPLINES, ConfigurationError, load_config, update_config_value
from .intake import run_intake
from .orchestration import (
    TransitionError,
    accept_slice,
    add_slice,
    advance_slice,
    approve_gate,
    begin_final_validation,
    confirm_discipline,
    mark_ready_for_handoff,
    record_intake,
    reject_slice,
    require_user_input,
    resolve_user_input,
    submit_architecture,
    submit_briefing,
)
from .routing import route_subject
from .provenance import register_derivation
from .storage import WorkspaceError, load_state, save_state, write_json
from .validation import validate_workspace_for_final
from .workspace import initialise_workspace, utc_now


def _workspace(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _load(path: str):
    workspace = _workspace(path)
    return workspace, load_state(workspace)


def _artifact_argument(workspace: Path, value: str) -> Path:
    """Accept an absolute, current-directory-relative, or workspace-relative path."""
    supplied = Path(value).expanduser()
    if supplied.is_absolute():
        return supplied
    current_candidate = supplied.resolve()
    try:
        current_candidate.relative_to(workspace.resolve())
        if current_candidate.exists():
            return current_candidate
    except ValueError:
        pass
    return workspace / supplied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assignment-assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a new assignment workspace")
    init.add_argument("workspace")

    start = sub.add_parser("start", help="Index sources and begin assignment intake")
    start.add_argument("workspace")

    status = sub.add_parser("status", help="Show current workflow state")
    status.add_argument("workspace")
    status.add_argument("--json", action="store_true", dest="as_json")

    task = sub.add_parser("next-task", help="Write the next Codex task packet")
    task.add_argument("workspace")

    confirm = sub.add_parser("confirm-discipline", help="Record an explicit discipline decision")
    confirm.add_argument("workspace")
    confirm.add_argument("discipline", choices=sorted(ALLOWED_DISCIPLINES - {"auto"}))

    capabilities = sub.add_parser("capabilities", help="Show extraction and verification capabilities")
    capabilities.add_argument("workspace")

    derived = sub.add_parser("register-derived", help="Register a transcript or reading copy")
    derived.add_argument("workspace")
    derived.add_argument("source")
    derived.add_argument("derived")
    derived.add_argument("--method", required=True)
    derived.add_argument(
        "--verification-status", choices=("unchecked", "checked"), default="unchecked"
    )

    briefing = sub.add_parser("submit-briefing", help="Register the Gate 1 briefing")
    briefing.add_argument("workspace")
    briefing.add_argument("artifact")

    architecture = sub.add_parser("submit-architecture", help="Register the Gate 2 architecture")
    architecture.add_argument("workspace")
    architecture.add_argument("artifact")

    approve = sub.add_parser("approve", help="Record a human gate approval")
    approve.add_argument("workspace")
    approve.add_argument("gate", choices=("gate1", "gate2"))
    approve.add_argument("--reviewer", default="user")
    approve.add_argument("--note", default="")

    create_slice = sub.add_parser("slice-create", help="Create a vertical slice")
    create_slice.add_argument("workspace")
    create_slice.add_argument("slice_id")
    create_slice.add_argument("title")
    create_slice.add_argument("--criterion", action="append", default=[])
    create_slice.add_argument("--word-budget", type=int)

    advance = sub.add_parser("slice-advance", help="Advance a slice by one valid state")
    advance.add_argument("workspace")
    advance.add_argument("slice_id")
    advance.add_argument("target")
    advance.add_argument("--artifact")

    accept = sub.add_parser("slice-accept", help="Record human acceptance of a reviewed slice")
    accept.add_argument("workspace")
    accept.add_argument("slice_id")
    accept.add_argument("--reviewer", default="user")
    accept.add_argument("--note", default="")

    reject = sub.add_parser("slice-reject", help="Route a failed slice to the responsible stage")
    reject.add_argument("workspace")
    reject.add_argument("slice_id")
    reject.add_argument(
        "failure",
        choices=(
            "citation_problem",
            "missing_research",
            "weak_argument",
            "wrong_premise",
            "writing_problem",
            "rubric_misalignment",
        ),
    )
    reject.add_argument("reason")
    reject.add_argument("--origin", choices=("internal", "user"), default="internal")

    require = sub.add_parser("require-input", help="Pause for authentic user input")
    require.add_argument("workspace")
    require.add_argument("prompt")

    resolve = sub.add_parser("resolve-input", help="Record a user's response")
    resolve.add_argument("workspace")
    resolve.add_argument("request_id")
    resolve.add_argument("response")

    finalise = sub.add_parser("begin-final-validation", help="Enter whole-assignment validation")
    finalise.add_argument("workspace")

    check = sub.add_parser("quality-check", help="Run deterministic state checks")
    check.add_argument("workspace")

    handoff = sub.add_parser("mark-ready", help="Record a passing quality report")
    handoff.add_argument("workspace")
    handoff.add_argument("report")
    return parser


def _print_status(state, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
        return
    print(f"Assignment: {state.assignment_id}")
    print(f"Phase: {state.phase}")
    print(f"Discipline: {state.routing.get('discipline', 'not yet routed')}")
    print(f"Sources: {state.source_manifest or 'not indexed'}")
    print(f"Slices: {len(state.slices)}")
    for record in state.slices.values():
        print(f"  {record.slice_id}: {record.status} — {record.title}")
    open_inputs = [item for item in state.user_inputs if item.status == "open"]
    print(f"Open user-input requests: {len(open_inputs)}")


def run(args: argparse.Namespace) -> int:
    command = args.command
    if command == "init":
        workspace = _workspace(args.workspace)
        state = initialise_workspace(workspace)
        print(f"Initialised {workspace}")
        print(f"Assignment ID: {state.assignment_id}")
        return 0

    workspace, state = _load(args.workspace)

    if command == "start":
        config = load_config(workspace / "assignment-assistant.yaml")
        result = run_intake(workspace)
        routing = route_subject(str(result["routing_text"]), str(config["discipline"]))
        record_intake(
            state,
            config,
            str(result["manifest_path"]),
            str(result["index_path"]),
            routing,
        )
        save_state(workspace, state)
        print(f"Indexed {result['manifest']['source_count']} files")
        print(f"Discipline suggestion: {routing['discipline']}")
        if routing["requires_confirmation"]:
            print("Discipline routing requires user confirmation")
        print("Next: produce and submit the Gate 1 assessment briefing")
        return 0

    if command == "status":
        _print_status(state, args.as_json)
        return 0

    if command == "next-task":
        task_text = CodexAdapter().render_next_task(workspace, state)
        task_dir = workspace / ".assignment-assistant" / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().replace(":", "").replace("+0000", "Z")
        target = task_dir / f"{stamp}-{uuid.uuid4().hex[:8]}-{state.phase.lower()}.md"
        target.write_text(task_text, encoding="utf-8")
        print(target)
        return 0

    if command == "capabilities":
        manifest_path = workspace / (
            state.capability_manifest or ".assignment-assistant/capabilities.json"
        )
        if not manifest_path.exists():
            manifest_path = write_capability_manifest(workspace)
            state.capability_manifest = manifest_path.relative_to(workspace).as_posix()
            save_state(workspace, state)
        print(manifest_path.read_text(encoding="utf-8"), end="")
        return 0

    if command == "register-derived":
        record = register_derivation(
            workspace,
            _artifact_argument(workspace, args.source),
            _artifact_argument(workspace, args.derived),
            args.method,
            args.verification_status,
        )
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0

    if command == "confirm-discipline":
        confirm_discipline(state, args.discipline)
        update_config_value(
            workspace / "assignment-assistant.yaml", "discipline", args.discipline
        )
        save_state(workspace, state)
        print(f"Discipline: {args.discipline}")
        return 0

    if command == "submit-briefing":
        submit_briefing(state, workspace, _artifact_argument(workspace, args.artifact))
    elif command == "submit-architecture":
        submit_architecture(state, workspace, _artifact_argument(workspace, args.artifact))
    elif command == "approve":
        approve_gate(state, args.gate, args.reviewer, args.note)
    elif command == "slice-create":
        add_slice(state, args.slice_id, args.title, args.criterion, args.word_budget)
    elif command == "slice-advance":
        artifact = _artifact_argument(workspace, args.artifact) if args.artifact else None
        advance_slice(state, workspace, args.slice_id, args.target, artifact)
    elif command == "slice-accept":
        accept_slice(state, args.slice_id, args.reviewer, args.note)
    elif command == "slice-reject":
        reject_slice(state, args.slice_id, args.failure, args.reason, args.origin)
    elif command == "require-input":
        request = require_user_input(state, args.prompt)
        print(f"User-input request: {request.request_id}")
    elif command == "resolve-input":
        resolve_user_input(state, args.request_id, args.response)
    elif command == "begin-final-validation":
        begin_final_validation(state)
    elif command == "quality-check":
        report = validate_workspace_for_final(workspace, state)
        report_dir = workspace / "assignment" / "final"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "quality-report.json"
        write_json(report_path, report)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 2
    elif command == "mark-ready":
        report_path = _artifact_argument(workspace, args.report).resolve()
        try:
            relative_report = report_path.relative_to(workspace.resolve()).as_posix()
        except ValueError as exc:
            raise WorkspaceError("Quality report must be inside the workspace") from exc
        if not report_path.is_file():
            raise WorkspaceError(f"Quality report does not exist: {report_path}")
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not payload.get("passed"):
            raise TransitionError("Quality report has not passed")
        mark_ready_for_handoff(state, relative_report)
    else:
        raise AssertionError(f"Unhandled command: {command}")

    save_state(workspace, state)
    print(f"Phase: {state.phase}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ConfigurationError, TransitionError, WorkspaceError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
