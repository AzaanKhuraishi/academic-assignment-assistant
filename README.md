# Academic Assignment Assistant

Academic Assignment Assistant lets a student work through an evidence-led
university assignment by talking to Codex. Codex handles the technical setup and
operates the protected workflow behind the scenes.

## Codex Quick Start

1. Connect GitHub to Codex and give Codex access to this repository.
2. Open this repository in a new Codex task.
3. Say: **“Set up Academic Assignment Assistant and start a new assignment.”**
4. When Codex asks, provide your assignment files, a ZIP source pack, or the
   location of a folder Codex can access.
5. Review Codex's interpretation and plan, then approve or correct them in the
   conversation as the work progresses.

That is the complete ordinary-user setup. The student does not need to install
anything manually, use a terminal, edit configuration files or understand the
workflow engine.

## What Codex does for the student

Codex reads `AGENTS.md`, checks the repository and computer, prepares an isolated
local environment, installs the internal engine and creates a private assignment
workspace. It then places the supplied materials in the correct location, indexes
them without altering the originals and starts the intake workflow.

Codex translates ordinary requests such as “start my assignment”, “I approve the
briefing”, “this argument needs more evidence” and “accept this section” into the
appropriate protected workflow operations. Command-line details remain hidden
unless the user explicitly asks to see them.

If automatic setup cannot finish, Codex explains the problem and the required next
step in plain language. It does not present a terminal dump as the user experience,
and it does not delete or overwrite the student's source files.

## What the student sees

- A request for the brief, rubric, teaching material and any supplied case files.
- A concise assessment briefing to approve or correct before answer design begins.
- A rubric-mapped assignment plan to approve or correct before prose drafting.
- Focused questions where personal experience, ambiguous instructions or a
  material decision require the student's input.
- Reviewable sections and clear feedback points as the assignment develops.
- A final quality-checked handoff. Submission always remains the student's action.

## Safeguards that remain active

- Supplied originals are preserved and exact duplicates are detected by SHA-256.
- Facts, external evidence, analysis and personal experience remain distinct.
- Gate 1 blocks progress until the student approves the interpretation.
- Gate 2 blocks drafting until the student approves the architecture and word budget.
- Rejected work is routed to the stage that caused the problem instead of receiving
  a superficial rewrite.
- Missing personal experience creates a hard pause for authentic student input.
- The system cannot submit work or impersonate the student.

## Advanced / Local / Developer Setup

The following section is for contributors and users who deliberately want to operate
the implementation themselves. Ordinary students can ignore it.

Python 3.9 or later is required. The core has no third-party runtime dependencies.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
assignment-assistant init workspace
```

Put the brief, rubric, teaching material and supplied case files into
`workspace/source/`, then run:

```bash
assignment-assistant start workspace
assignment-assistant next-task workspace
assignment-assistant status workspace
```

The Codex bootstrap used for the conversational experience is also available to
developers:

```bash
python3 scripts/codex_bootstrap.py --workspace workspace
python3 scripts/codex_bootstrap.py --workspace workspace \
  --source "/path/to/source-pack.zip" --start
```

The installer may fetch standard Python build tooling (`setuptools` and `wheel`) if
it is not already available. Run `assignment-assistant --help` for the full internal
command surface. See `docs/codex-operations.md` for the natural-language mapping used
by Codex and `CONTRIBUTING.md` for development guidance.

## Technical architecture

The executable architecture remains the source of workflow truth. Markdown defines
the academic method and specialist contracts; Python executes the state machine,
records approvals, indexes sources and routes rejected work to the responsible stage.

- `ACADEMIC_WORKFLOW.md` — canonical universal method
- `AGENTS.md` — Codex entry point and automatic-operation contract
- `ARCHITECTURE.md` — system design and state model
- `agents/contracts/` — bounded specialist responsibilities
- `overlays/` — discipline-specific additions
- `policies/` — evidence, integrity, privacy and quality rules
- `scripts/codex_bootstrap.py` — idempotent Codex setup and source-pack intake
- `src/assignment_assistant/` — executable workflow engine
- `templates/` — reusable workspace artefacts
- `examples/` — synthetic demonstrations only
- `tests/` — unit and end-to-end workflow tests

## Current scope

The Codex adapter operates inside an authorised Codex environment; it does not call
a hosted model API itself. Plain text, Markdown, DOCX, PPTX and ODT can be indexed or
converted with dependency-free extractors. PDFs are preserved and flagged for a
capable PDF extractor. Video is preserved and flagged for transcription. A runtime
must register generated reading copies and transcripts with provenance before their
content is treated as read.

Real assignments belong in the ignored `workspace/` directory or another private
location. Never commit course files, private cases, personal data, drafts or model
state. The repository examples are fictional.

## Licence

Apache License 2.0. See `LICENSE`.
