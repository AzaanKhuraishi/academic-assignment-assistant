# Academic Assignment Assistant

Academic Assignment Assistant is a local-first workflow engine for evidence-led
university work. It turns a folder of assignment material into an auditable process:
intake, interpretation, architecture, research, vertical-slice development,
validation and user handoff.

The project is deliberately more than a prompt collection. Markdown defines the
academic method and specialist contracts; Python executes the state machine,
records approvals, indexes sources and routes rejected work to the responsible stage.

## What it protects

- Supplied originals are indexed without being overwritten.
- Exact duplicate files are identified by SHA-256.
- Facts, analysis, external evidence and user experience remain distinguishable.
- Gate 1 prevents work from proceeding on a misread brief.
- Gate 2 prevents prose drafting before the argument and word budget are approved.
- Missing personal experience creates a hard user-input pause.
- The system ends at a reviewable handoff. It does not submit work for the student.

## Quick start

Python 3.9 or later is sufficient; the core has no third-party runtime dependencies.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
assignment-assistant init workspace
```

The installer may fetch standard Python build tooling (`setuptools` and `wheel`) when
it is not already available. The application itself has no third-party runtime
dependencies.

Put the brief, rubric, teaching material and supplied case files into
`workspace/source/`, then run:

```bash
assignment-assistant start workspace
assignment-assistant next-task workspace
assignment-assistant status workspace
```

If automatic routing is weak or mixed, the task packet stops and asks the user to
confirm a discipline. The decision is recorded with:

```bash
assignment-assistant confirm-discipline workspace consultancy
```

Inspect the built-in and runtime-required capabilities with:

```bash
assignment-assistant capabilities workspace
```

In Codex, the beginner-facing instruction is simply:

> Start assignment intake in `workspace` and follow the repository workflow.

Codex reads `AGENTS.md`, runs the intake command, prepares the Gate 1 briefing and
stops for the user's review.

## Human approval flow

After the runtime produces `assignment/briefing/ASSESSMENT_BRIEFING.md`:

```bash
assignment-assistant submit-briefing workspace \
  workspace/assignment/briefing/ASSESSMENT_BRIEFING.md
assignment-assistant approve workspace gate1 --reviewer user
```

After the approved interpretation has been turned into an architecture:

```bash
assignment-assistant submit-architecture workspace \
  workspace/assignment/working/ASSIGNMENT_ARCHITECTURE.md
assignment-assistant approve workspace gate2 --reviewer user
```

The runtime then creates and develops vertical slices. Moving from `USER_REVIEW` to
`ACCEPTED` requires the dedicated human-recording command:

```bash
assignment-assistant slice-accept workspace diagnosis --reviewer user
```

Run `assignment-assistant --help` for the remaining slice, rejection and
final-validation commands.

## Repository map

- `ACADEMIC_WORKFLOW.md` — canonical universal method
- `AGENTS.md` — concise instructions for Codex
- `ARCHITECTURE.md` — system design and state model
- `agents/contracts/` — bounded input/output contracts
- `overlays/` — discipline-specific additions
- `policies/` — evidence, integrity, privacy and quality rules
- `src/assignment_assistant/` — executable workflow engine
- `templates/` — reusable workspace artefacts
- `examples/` — synthetic demonstrations only
- `tests/` — unit and end-to-end workflow tests

## Scope of version 0.1

The current Codex adapter produces state-aware task packets for an existing Codex
environment. It does not call a hosted model API. Plain text, Markdown, DOCX, PPTX
and ODT can be indexed or converted with the dependency-free extractors. PDFs are
preserved and flagged for a capable PDF extractor; video is preserved and flagged
for transcription. These capability gaps are explicit so unread material cannot be
silently treated as understood.

For a PDF, DOCX or PPTX final deliverable, copy the generated
`.assignment-assistant/templates/visual-inspection.json` into `assignment/final/`,
record the rendered files that were inspected, and set `passed` only after the visual
review is complete. The quality gate blocks handoff without this record.

When a runtime creates a PDF reading copy or media transcript, place it under
`derived/` and register both hashes and the method:

```bash
assignment-assistant register-derived workspace source/lecture.mp4 \
  derived/transcripts/lecture.md --method "checked speech-to-text" \
  --verification-status checked
```

## Privacy and repository hygiene

Real assignments belong in an ignored `workspace/` or in a directory outside this
repository. Never commit course files, private cases, personal data, drafts or model
state. The examples in this repository are fictional.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

See `CONTRIBUTING.md` for extension rules and `docs/adding-overlays.md` for adding a
discipline overlay.

## Licence

Apache License 2.0. See `LICENSE`.
