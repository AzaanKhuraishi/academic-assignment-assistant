# Human validation

Human approval is a control boundary, not a ceremonial acknowledgement.

## Mandatory gates

- Gate 1 confirms the interpretation of the brief, rubric and constraints.
- Gate 2 confirms the argument architecture, rubric coverage and word budget.
- `USER_REVIEW` permits acceptance or rejection of each slice when configured.
- Final handoff allows the user to inspect the complete document before submission.

## Hard user-input pause

Use `REQUIRES_USER_INPUT` when the work depends on personal experience, an inaccessible
source, a material strategic choice, ambiguous instructions or repeated failed
validation. Preserve the exact question and response in state. Never infer that a
general approval verifies a specific personal claim.
