"""Ties every test step to a row in test_cases.csv, so no step can be skipped silently.

Use it in tests like this:
    with step("OC-05"):
        ...actions and asserts for that step...

- The step name and expected result come from test_cases.csv and appear in the Allure report.
- An ID that is not in the CSV raises an error at once (catches typos).
- conftest.py prints which steps passed, failed or were never reached, and saves it to reports/.
"""
import contextlib
import csv
from pathlib import Path

import allure

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "test_cases.csv"            # patient app; doctor app rows go in test_cases_doctor.csv
STARTED: set = set()
PASSED: set = set()


def load_cases():
    """Rows of every test_cases*.csv: test_cases.csv (patient app) and test_cases_doctor.csv (doctor app)."""
    rows = []
    for path in sorted(ROOT.glob("test_cases*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as f:  # utf-8-sig: works after saving from Excel
            rows += [row for row in csv.DictReader(f) if row.get("step_id", "").strip()]
    return rows

def is_automated(row):
    return row["automated"].strip().lower() == "yes"


_CASES = {row["step_id"].strip(): row for row in load_cases()}


@contextlib.contextmanager
def step(step_id):
    row = _CASES.get(step_id)
    if row is None:
        raise KeyError(f"{step_id} is not in test_cases.csv. Add the row there first.")
    STARTED.add(step_id)
    with allure.step(f"{step_id}: {row['step']}  ->  expect: {row['expected_result']}"):
        yield
    PASSED.add(step_id)
