# Workflow graph

The student begins with a natural-language request in Codex. Codex completes setup,
places the supplied source material and operates the executable workflow internally.
The orchestrator advances only when the artefact required by the present state exists.
Gate approvals and user-input resolutions are first-class state records.

```text
conversation → automatic setup → source request → intake
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

An adapter translates conversation and proposes work; the state machine authorises
transitions. This prevents an agent from bypassing a gate merely by writing a
later-stage file. Command execution is invisible to the ordinary user, while every
transition remains auditable.
