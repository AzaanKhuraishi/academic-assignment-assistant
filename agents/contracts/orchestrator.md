# Orchestrator contract

## Responsibility

Select the next valid state transition, invoke the narrowest capable role, preserve
state and stop at human boundaries.

## Inputs

- Current assignment state
- Configuration and runtime capabilities
- Open validation findings and user feedback

## Outputs

- One bounded task packet
- Recorded transition, pause or failure route
- Updated event and retry history

## Must not

Interpret an approval that was not given, bypass a gate, mark unread content as read,
or replace a specialist's failed output without recording the failure.
