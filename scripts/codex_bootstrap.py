#!/usr/bin/env python3
"""Run the Codex bootstrap directly from a fresh repository checkout."""

from pathlib import Path
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from assignment_assistant.bootstrap import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
