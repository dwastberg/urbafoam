"""End-to-end regression tests: setup + postprocess must reproduce tests/golden/."""
import pytest

from tests.regression import CASES, GOLDEN, compare_snapshot, run_case, snapshot


@pytest.mark.parametrize("name", sorted(CASES))
def test_setup_and_postprocess_match_golden(name, tmp_path):
    case_dir = run_case(name, tmp_path / "case")
    snapshot(case_dir, tmp_path / "snapshot")
    problems = compare_snapshot(tmp_path / "snapshot", GOLDEN / name)
    assert not problems, "\n".join(problems)
