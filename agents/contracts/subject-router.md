# Subject Router contract

## Responsibility

Select the smallest applicable discipline overlay after intake.

## Inputs

- Filenames and extracted source text
- Explicit discipline configuration, if any
- Explainable routing scores and matched terms

## Outputs

- Selected overlay
- Confidence and evidence for the decision
- Confirmation request when the evidence is weak or mixed

## Must not

Classify before intake, conceal mixed evidence, or load multiple complete overlays when
one overlay plus a focused secondary rule is sufficient.
