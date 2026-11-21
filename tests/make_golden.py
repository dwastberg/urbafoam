"""Regenerate tests/golden/ from the current code. Review the git diff of tests/golden afterwards!

    uv run python -m tests.make_golden
"""
import tempfile
from pathlib import Path

from tests.regression import CASES, GOLDEN, run_case, snapshot


def main():
    for name in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = run_case(name, Path(tmp) / name)
            snapshot(case_dir, GOLDEN / name)
        print(f"wrote {GOLDEN / name}")


if __name__ == "__main__":
    main()
