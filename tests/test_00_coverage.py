"""Runs without a phone. Fails if test_cases.csv and the test code disagree, so a step can't be forgotten."""
import re
from collections import Counter
from pathlib import Path

import pytest

from utils.steps import is_automated, load_cases

TESTS_DIR = Path(__file__).parent
STEP_CALL = re.compile(r'step\(\s*"([A-Z]+-\d+)"\s*\)')

pytestmark = pytest.mark.offline


def _step_ids_in_code():
    ids = []
    for f in sorted(TESTS_DIR.glob("test_*.py")):
        if f.name != Path(__file__).name:
            ids += STEP_CALL.findall(f.read_text(encoding="utf-8"))
    return ids


def test_csv_step_ids_are_unique():
    counts = Counter(row["step_id"].strip() for row in load_cases())
    dupes = [sid for sid, n in counts.items() if n > 1]
    assert not dupes, f"Duplicate step_id in test_cases.csv: {dupes}"


def test_every_automated_step_has_code():
    automated = {row["step_id"].strip() for row in load_cases() if is_automated(row)}
    missing = sorted(automated - set(_step_ids_in_code()))
    assert not missing, f"Marked automated=yes in test_cases.csv but no step() in any test: {missing}"


def test_no_code_for_unknown_or_manual_steps():
    cases = {row["step_id"].strip(): row for row in load_cases()}
    in_code = set(_step_ids_in_code())
    unknown = sorted(in_code - cases.keys())
    manual = sorted(sid for sid in in_code & cases.keys() if not is_automated(cases[sid]))
    assert not unknown, f"step() IDs not in test_cases.csv: {unknown}"
    assert not manual, f"Steps marked automated=no but used in code (change the CSV to yes): {manual}"


def test_each_step_used_once():
    counts = Counter(_step_ids_in_code())
    dupes = [sid for sid, n in counts.items() if n > 1]
    assert not dupes, f"Same step ID used twice in the tests (copy-paste?): {dupes}"
