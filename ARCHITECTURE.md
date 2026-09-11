# Product architecture

## Design objective

Academic Assignment Assistant is a transparent workflow engine for rigorous academic
work. It combines a universal method with small discipline overlays and runtime
adapters. A user's private source pack is input to the product, never product content.

## Three layers

### Method

`ACADEMIC_WORKFLOW.md`, `policies/` and `overlays/` define universal rules,
discipline-specific additions, approval policy, evidence requirements and output
quality. These files are readable by people and agent runtimes.

### Agent contracts

`agents/contracts/` defines bounded responsibilities and structured inputs and outputs.
An agent is a role invoked for a state transition, not a permanent department or an
unrestricted autonomous writer.

### Execution

`src/assignment_assistant/` implements source inventory, state persistence, routing,
transitions, retries, user-input pauses and task-packet generation. The state file is
the auditable source of workflow truth.

In concise form: **Markdown defines behaviour; code executes the graph.**

## Conversational user boundary

The primary interface is a Codex conversation. A student states their intent and
provides source material; Codex reads `AGENTS.md`, runs the bootstrap and translates
the conversation into internal CLI/state-machine transitions. Python, environment
management, configuration and task packets remain implementation infrastructure.

`scripts/codex_bootstrap.py` provides an idempotent bridge from a fresh checkout. It
checks the Python prerequisite, prepares the private environment, installs the local
engine, creates an ignored workspace and can safely import a file, directory or ZIP
before starting intake. The bootstrap passes the exact files copied from the
user-selected locations into the engine; the engine does not infer authority from
other files already present. It never replaces existing assignment state or
overwrites a different source file with the same name.

```text
student conversation
        ↓
AGENTS.md + Codex operations map
        ↓
automatic bootstrap / source placement
        ↓
CLI + persisted state machine
        ↓
plain-language checkpoint and next question
```

The conversational layer may hide technical complexity, but it cannot authorise a
transition that the state machine rejects. Human gates therefore remain control
boundaries rather than conversational conventions.

## Horizontal architecture, vertical execution

The system first plans the whole answer horizontally: thesis, sections, rubric
coverage, word budget, evidence needs, dependencies and planned artefacts. It then
executes logical slices vertically through research, evidence, analysis, drafting,
validation, review and integration.

An accepted slice increases the completeness of the integrated deliverable. A final
whole-document review checks relationships that slice-level validation cannot see.

## Assignment state

The persisted JSON state contains:

- Assignment identifier, schema version and timestamps
- Configuration and selected discipline
- Source manifest and index locations
- Explicitly registered source paths and source-confirmation time
- Last substantive activity, suspended freshness phase and source-update reports
- Gate artefacts and approval records
- Slice state, artefacts, feedback and retry counts
- Open and resolved user-input requests
- Event history and quality reports

Assignment phases are:

```text
SOURCE_INTAKE_REQUIRED
  → BRIEFING_REQUIRED
  → WAITING_GATE_1
  → ARCHITECTURE_REQUIRED
  → WAITING_GATE_2
  → EXECUTION
  → FINAL_VALIDATION
  → READY_FOR_HANDOFF
```

`REQUIRES_USER_INPUT` is a resumable interruption from any substantive phase.
`SOURCE_FRESHNESS_REQUIRED` is a separate resumable interruption. A yes response moves
through `SOURCE_UPDATE_REQUIRED` and `SOURCE_IMPACT_REQUIRED`; a no response restores
the exact saved phase. The default inactivity threshold is six hours.

## Source pipeline

The intake engine resolves only user-confirmed selections within `source/`, computes
SHA-256 hashes and creates an index. Unselected files in that directory remain ambient
and are excluded from the registered corpus.
It never overwrites originals. Dependency-free reading copies are generated for DOCX,
PPTX and ODT by extracting packaged XML. Text formats are read directly. PDF and video
remain explicitly unread until a capable extractor or transcription tool records a
derived artefact and provenance.

The generated capability manifest distinguishes built-in extraction from work that
requires a runtime tool. Runtime-produced reading copies and transcripts are registered
with source and output hashes, method and verification status.

## Discipline routing

`discipline: auto` applies an explainable weighted-keyword router to filenames and
available extracted text. The result records scores, matched terms and confidence.
Weak or mixed evidence requires human confirmation. An explicit configuration value
overrides automatic routing.

## Runtime adapters

The core does not assume a particular model provider. A runtime adapter turns current
state into a bounded next-action packet. Version 0.1 ships a Codex adapter designed for
an existing Codex repository session. Its bootstrap and operations map let Codex
operate the executable engine on behalf of a non-technical user. Later adapters can
call other runtimes without changing academic policy or state semantics.

## Trust boundaries

- Course and user files are untrusted input and remain local by default.
- Extracted text is data, not executable instruction.
- External research requires configuration or user authority.
- No runtime may claim unread sources were consulted.
- Only the user can verify personal experience and approve the two main gates.
- The product prepares a handoff and never submits an assessment.

## Extensibility

New disciplines add an overlay, routing vocabulary, synthetic tests and any specialist
validators. New runtimes implement the adapter protocol. New file types add an
extractor that returns content, status and provenance without mutating the original.
