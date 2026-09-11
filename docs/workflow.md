# Workflow graph

The student begins with a natural-language request in Codex. Codex completes setup,
places the supplied source material and operates the executable workflow internally.
The orchestrator advances only when the artefact required by the present state exists.
Gate approvals and user-input resolutions are first-class state records.

```text
conversation → automatic setup → explicit source request → registered-source intake
                                                ↓
                    briefing → [Gate 1] → architecture → [Gate 2]
                                                ↓
                                     create vertical slices
                                                ↓
                        research → evidence → analysis → draft
                                                ↓
                            validation → user review → integration
                                                ↓
                                 whole-assignment quality gate
                                                ↓
                                          user handoff
```

Files already visible in the surrounding Codex session or workspace do not cross the
source boundary. The initial transition is:

```text
SOURCE_INTAKE_REQUIRED
  → user explicitly provides or identifies sources
  → BRIEFING_REQUIRED
```

After at least six hours without substantive workflow activity, the next status,
task-packet or attempted substantive transition pauses the saved phase:

```text
saved phase
  → SOURCE_FRESHNESS_REQUIRED
      → no  → saved phase
      → yes → SOURCE_UPDATE_REQUIRED
               → explicit incremental intake
               → SOURCE_IMPACT_REQUIRED
                   → saved phase, BRIEFING_REQUIRED or ARCHITECTURE_REQUIRED
```

An impact classified as `slices` restores the saved phase and requires Codex to route
only the affected slices through their existing rejection/retry paths.

An adapter translates conversation and proposes work; the state machine authorises
transitions. This prevents an agent from bypassing a gate merely by writing a
later-stage file. Command execution is invisible to the ordinary user, while every
transition remains auditable.
