# Academic Assignment Assistant — Codex entry point

The user's instructions take precedence over repository guidance. Read
`ACADEMIC_WORKFLOW.md` and `ARCHITECTURE.md` before running an assignment workflow.
Read only the selected discipline overlay and the agent contract needed for the
current state.

## When operating on an assignment

1. Run `assignment-assistant start <workspace>` before interpreting source material.
2. Consult `<workspace>/SOURCE_INDEX.md`; do not ingest exact duplicate placements.
3. Read governing documents completely. Use derived text for ordinary reading and
   originals when layout, images, equations, notes or exact wording matter.
4. Produce the Gate 1 briefing and stop for explicit user approval.
5. Produce the rubric-mapped architecture and stop for explicit user approval.
6. Develop approved vertical slices through the recorded state sequence.
   Use the evidence-matrix, research-log and vertical-slice templates generated under
   `<workspace>/.assignment-assistant/templates/`.
7. Route a failed slice to the responsible stage; preserve feedback and retry history.
8. Stop in `REQUIRES_USER_INPUT` when personal experience, a material choice or
   inaccessible evidence cannot be verified.
9. Run the whole-assignment quality gate and visually inspect layout-dependent output.
10. Hand the work to the user. Never submit or impersonate the user.

Never fabricate facts, quotations, references, page numbers, data, access dates,
interviews or personal experience. Keep originals read-only. Keep real assignment
content outside version control.

## When developing this product

Preserve the separation between policy Markdown, executable orchestration and runtime
adapters. Keep the core dependency-free unless a fully justified feature requires a
dependency. Add meaningful tests for state transitions, source safety and rejection
routing. Do not place real course material in fixtures or examples.
