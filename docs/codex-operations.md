# Codex conversational operations

This file is an internal operating guide for Codex. It maps a student's ordinary
language to the executable workflow without exposing implementation details in the
normal conversation.

## Operating rule

Codex performs commands itself and reports the outcome, current checkpoint and next
student decision in plain language. Use the virtual-environment Python directly so
activation is unnecessary:

```text
.venv/bin/python -m assignment_assistant <operation> ...
```

On Windows, use `.venv\Scripts\python.exe`. Generate `next-task` after each successful
transition and follow the contract and overlay named in that packet.

Never interpret politeness, silence or an unrelated “okay” as approval. Approval must
refer clearly to the briefing, architecture or reviewed slice currently presented.

## Setup and intake

| Student intent | Codex action | Student-facing response |
|---|---|---|
| “Set it up” or “start a new assignment” | Run the bootstrap without `--start` | Confirm readiness and ask for the assignment/source materials |
| Provides files, a folder or a ZIP | Run the bootstrap with one or more `--source` values and `--start` | State how many files were added, identify unreadable formats or duplicates, and explain the next review step |
| Provides more material before Gate 1 | Preserve it under `workspace/source/`, then rerun intake if the current state permits it | Confirm what was added and whether it changes the briefing |
| “Where are we?” or “what next?” | Run `status` and `next-task` internally | Explain the current phase and the one decision or action needed next |

If `workspace/` already contains state, inspect it before acting. Resume when that is
the user's intention. For a genuinely new assignment, create a separately named
ignored workspace rather than deleting or replacing the existing one.

## Main approval gates

| Student intent | Required internal operation | Behaviour |
|---|---|---|
| “I approve the briefing” | `approve <workspace> gate1 --reviewer user` | Record Gate 1 approval and begin architecture work |
| Corrects or rejects the briefing | Revise and resubmit the briefing; do not approve | Show the corrected interpretation and ask again |
| “I approve the plan/architecture” | `approve <workspace> gate2 --reviewer user` | Record Gate 2 approval and begin vertical execution |
| Corrects or rejects the architecture | Revise and resubmit the architecture; do not approve | Show the revised plan, rubric map and word budget |

The briefing and architecture artefacts must already be registered through the state
machine before their approvals can be recorded. Do not create an approval record from
ambiguous language.

## Slice review and feedback

| Student feedback | Internal route |
|---|---|
| “I accept this section/slice” | `slice-accept` after the slice has reached `USER_REVIEW` |
| A citation is wrong or unsupported | `slice-reject ... citation_problem ... --origin user` |
| More research is needed | `slice-reject ... missing_research ... --origin user` |
| The reasoning or evaluation is weak | `slice-reject ... weak_argument ... --origin user` |
| The premise, scope or interpretation is wrong | `slice-reject ... wrong_premise ... --origin user` |
| The writing is unclear or poorly structured | `slice-reject ... writing_problem ... --origin user` |
| The work misses the rubric or learning outcome | `slice-reject ... rubric_misalignment ... --origin user` |

After rejection, return to the state selected by the retry policy. Correct the cause,
preserve the feedback and retry count, and present the revised slice for review. Do
not merely polish the wording when the recorded problem concerns evidence, analysis,
scope or rubric alignment.

## Authentic user input

When progress depends on a personal experience, an inaccessible source, a material
choice or ambiguous instruction, record `require-input` and ask one focused question.
After the user answers, preserve their wording and provenance, record `resolve-input`
and resume the stored phase. Do not transform an unverified personal claim into an
external fact.

## Final validation and handoff

When every slice is integrated, enter final validation and run the deterministic
quality check. Complete any required citation, word-count and rendered-document
inspection. `mark-ready` is permitted only with a passing report. Give the student the
deliverable, compliance summary and unresolved caveats; never upload or submit the
assessment on their behalf.

## Failure translation

| Internal problem | Plain-language explanation |
|---|---|
| No supported Python launcher | “Automatic setup needs Python 3.9 or later, and it is not currently available on this computer.” |
| Environment or installation failure | “Codex could not finish preparing the private working environment. Your assignment files were not changed.” |
| Source path cannot be read | “Codex cannot access that file or folder yet. Please attach it here or grant access to its location.” |
| Unsafe or damaged ZIP | “The source pack could not be opened safely. Please provide a fresh ZIP or the uncompressed folder.” |
| Empty source set | “The workspace is ready, but no assignment materials were found. Please provide the brief and related files.” |
| Unsupported or unreadable format | “The file has been preserved, but its contents have not yet been read. Codex needs an appropriate extractor or transcript before relying on it.” |
| Invalid workflow transition | “That step cannot be recorded yet because an earlier review or approval is still required.” |

Codex may provide technical details afterwards if the student requests them.
