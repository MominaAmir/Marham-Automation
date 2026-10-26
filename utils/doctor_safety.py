"""Doctor app safety: the tests may only act while logged in as DOCTOR_NAME.
Questions are asked in the PowerShell window - run with -s. No keyboard = the safe answer."""
import contextlib
import sys

import pytest

import re

from doctor_test_data import DOCTOR_APP_NAME


def doctor_stop(reason):
    pytest.exit(f"SAFETY STOP: {reason}. Nothing more was changed.", returncode=3)


def _normalise(name):
    """'DR. UNAIZA NISAR TESTING' and 'Dr. Unaiza Nisar Testing' -> 'unaiza nisar testing'"""
    name = re.sub(r"^\s*(prof\.?\s+)?(dr|doctor)\.?\s*", "", (name or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def check_doctor(shown_name):
    """The doctor app must show the test doctor's name; anything else stops the whole run."""
    if not shown_name or _normalise(shown_name) != _normalise(DOCTOR_APP_NAME):
        doctor_stop(f"doctor app shows '{shown_name}', not the test doctor '{DOCTOR_APP_NAME}'")


def require_marker_selected(config, marker):
    """Tests that log out or need typing only run when chosen on purpose: pytest -m <marker> -s"""
    if marker not in (config.getoption("markexpr") or ""):
        pytest.skip(f"Runs only when chosen on purpose: pytest -m {marker} -s")


@contextlib.contextmanager
def _console(config):
    capman = config.pluginmanager.getplugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)
    try:
        yield sys.stdin is not None and sys.stdin.isatty()
    finally:
        if capman:
            capman.resume_global_capture()


def ask_text(config, question):
    """Text typed by the tester (phone number, OTP). No keyboard = ''."""
    with _console(config) as keyboard:
        if not keyboard:
            print(f"\n{question} -> nobody at the keyboard")
            return ""
        return input(f"\n{question}: ").strip()

def ask_secret(config, question):
    """Like ask_text, but the typing is hidden (passwords). No keyboard = ''."""
    import getpass
    with _console(config) as keyboard:
        if not keyboard:
            print(f"\n{question} -> nobody at the keyboard")
            return ""
        return getpass.getpass(f"\n{question}: ").strip()