# Contributing

Keep changes small, auditable and covered by meaningful tests. Do not commit real
student work, institutional course content, credentials or personal data.

Before proposing a change:

1. Read `ARCHITECTURE.md` and the affected policy or contract.
2. Preserve the two human gates and the authentic-input pause.
3. Keep source processing read-only and record derivation provenance.
4. Add synthetic fixtures for new formats or disciplines.
5. Run `PYTHONPATH=src python -m unittest discover -s tests -v`.

Changes that weaken evidence, citation, integrity or source-safety rules require an
explicit architectural decision and must not be hidden in an adapter.
