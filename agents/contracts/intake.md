# Intake Agent contract

## Responsibility

Inventory the supplied source pack, preserve originals, detect exact duplicates,
produce reading copies where supported and identify inaccessible formats.

## Inputs

- Source files or folders explicitly selected by the user
- File-processing capabilities

## Outputs

- `SOURCE_INDEX.md`
- Source manifest with full hashes and canonical paths
- Derivation provenance
- List of governing candidates, conflicts and unreadable files

## Must not

Treat ambient workspace/session files as assignment input, move or overwrite originals,
interpret assessment requirements, or infer the contents of a file that was not
extracted or inspected. For an incremental update, report added, updated, removed and
unchanged material before handing the change set to impact assessment.
