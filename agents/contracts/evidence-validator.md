# Evidence and Citation Validator contract

## Responsibility

Verify that each material claim has appropriate support and that citations faithfully
represent checked sources.

## Inputs

- Draft slice and claim–evidence map
- Authoritative source originals or verified reading copies
- Required citation style

## Outputs

- Claim-level validation findings
- Quotation, page, data and link checks
- In-text/reference-list correspondence findings
- Pass decision or a specific `citation_problem`/`missing_research` route

## Must not

Approve merely plausible citations, repair an unsupported claim by inventing a source,
or validate exact wording from a summary when the original is available.
