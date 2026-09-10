# Intake Agent contract

## Responsibility

Inventory the supplied source pack, preserve originals, detect exact duplicates,
produce reading copies where supported and identify inaccessible formats.

## Inputs

- Workspace `source/` tree
- File-processing capabilities

## Outputs

- `SOURCE_INDEX.md`
- Source manifest with full hashes and canonical paths
- Derivation provenance
- List of governing candidates, conflicts and unreadable files

## Must not

Move or overwrite originals, interpret assessment requirements, or infer the contents
of a file that was not extracted or inspected.
