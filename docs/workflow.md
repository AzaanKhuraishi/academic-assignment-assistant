# Workflow graph

The orchestrator advances only when the artefact required by the present state exists.
Gate approvals and user-input resolutions are first-class state records.

```text
init → intake → briefing → [Gate 1] → architecture → [Gate 2]
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

An adapter proposes work; the state machine authorises transitions. This prevents an
agent from bypassing a gate merely by writing a later-stage file.
