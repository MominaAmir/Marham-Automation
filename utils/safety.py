"""Booking safety: the scripts may only ever book DOCTOR_NAME at HOSPITAL."""
import re

import pytest

from test_data import ALLOW_PC_BOOKING, DOCTOR_NAME, HOSPITAL


def _normalise(name):
    name = re.sub(r"^\s*(prof\.?\s+)?(dr|doctor)\.?\s*", "", name.strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def is_test_doctor(name):
    return bool(name) and _normalise(name) == _normalise(DOCTOR_NAME)


def stop_run(reason):
    pytest.exit(f"SAFETY STOP: {reason}. Nothing was booked.", returncode=3)


def require_pc_booking_allowed():
    if not ALLOW_PC_BOOKING:
        pytest.skip("PC booking is switched off (ALLOW_PC_BOOKING = False in test_data.py).")
    if not DOCTOR_NAME.strip() or not HOSPITAL.strip():
        stop_run("DOCTOR_NAME or HOSPITAL is empty in test_data.py")


def check_profile_is_test_doctor(shown_name):
    if not is_test_doctor(shown_name):
        stop_run(f"opened profile is '{shown_name}', not the test doctor '{DOCTOR_NAME}'")


def check_before_booking(page):
    """Called by ConfirmationPage.confirm() just before the booking button is tapped."""
    if not ALLOW_PC_BOOKING:
        stop_run("tried to confirm a booking while ALLOW_PC_BOOKING is False")
    if not page.has_text(DOCTOR_NAME, timeout=5):
        stop_run(f"confirm screen does not show the test doctor '{DOCTOR_NAME}'")
    if not page.has_text(HOSPITAL, timeout=5):
        stop_run(f"confirm screen does not show the test clinic '{HOSPITAL}'")



# ---------- Paid OC booking (Video Consultation + Marham Wallet) ----------
import sys

from test_data import ALLOW_OC_PAYMENT, OC_FEE, TEST_PATIENT_NAME

_bookings_this_run = 0


def require_oc_payment_allowed():
    if not ALLOW_OC_PAYMENT:
        pytest.skip("Paid OC booking is switched off (ALLOW_OC_PAYMENT = False in test_data.py).")


def _ask_yes(config, question):
    """Ask in the PowerShell window. No keyboard (unattended run) = NO."""
    capman = config.pluginmanager.getplugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)
    try:
        if not (sys.stdin and sys.stdin.isatty()):
            print(f"\n{question} -> nobody at the keyboard, answering NO")
            return False
        return input(f"\n{question} Type yes to continue: ").strip().lower() == "yes"
    finally:
        if capman:
            capman.resume_global_capture()


def allow_new_booking(config):
    """One booking per run. A second one only if you type yes."""
    global _bookings_this_run
    if _bookings_this_run >= 1:
        if not _ask_yes(config, f"{_bookings_this_run} booking was already made in this run. Book ANOTHER one?"):
            stop_run("a second booking in the same run was not approved")
    _bookings_this_run += 1


def check_popup_before_booking(summary, time_text, patient, fee=OC_FEE):
    """The Appointment Details pop-up must show exactly what we intend to book."""
    for label, value in (("doctor", DOCTOR_NAME), ("patient", patient),
                         ("fee", f"Rs. {fee}"), ("time", time_text)):
        if not summary.popup_has(value):
            stop_run(f"Appointment Details pop-up does not show the {label} '{value}'")


# ---------- Who is the booking for? ----------
from test_data import FAMILY_MEMBERS

_chosen_patient = None


def choose_patient(config):
    """Ask once per run: Self or a family member. No keyboard = Self. A retry reuses the same answer."""
    global _chosen_patient
    if _chosen_patient:
        return _chosen_patient
    options = [TEST_PATIENT_NAME] + list(FAMILY_MEMBERS)
    _chosen_patient = TEST_PATIENT_NAME
    capman = config.pluginmanager.getplugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)
    try:
        if sys.stdin and sys.stdin.isatty():
            print("\nWho should this booking be for?")
            for number, name in enumerate(options, start=1):
                print(f"  {number}) {name}{' (Self)' if number == 1 else ''}")
            for _ in range(3):
                answer = input("Type a number and press Enter [1]: ").strip() or "1"
                if answer.isdigit() and 1 <= int(answer) <= len(options):
                    _chosen_patient = options[int(answer) - 1]
                    break
                print(f"Please type a number from 1 to {len(options)}.")
        print(f"Booking for: {_chosen_patient}")
    finally:
        if capman:
            capman.resume_global_capture()
    return _chosen_patient



# ---------- Late doctor (OC): ask what to do, one cancellation per run ----------
LATE_ACTIONS = [
    ("cancel", "Cancel & Refund  (REAL: cancels this booking and asks for the refund)"),
    ("wait", "Wait More for 5 Minutes"),
    ("reschedule", "Reschedule - only check the 'Same doctor' screens (nothing is changed)"),
    ("none", "Nothing - only the checks already done"),
]
_late_action = None
_cancels_this_run = 0


def ask_choice(config, question, options, default=0):
    """Numbered menu in PowerShell; returns the chosen number - 1. No keyboard = the default."""
    capman = config.pluginmanager.getplugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)
    try:
        if not (sys.stdin and sys.stdin.isatty()):
            print(f"\n{question} -> nobody at the keyboard, using: {options[default]}")
            return default
        print(f"\n{question}")
        for number, text in enumerate(options, start=1):
            print(f"  {number}) {text}")
        for _ in range(3):
            answer = input(f"Type a number and press Enter [{default + 1}]: ").strip() or str(default + 1)
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            print(f"Please type a number from 1 to {len(options)}.")
        return default
    finally:
        if capman:
            capman.resume_global_capture()


def choose_late_action(config):
    """Asked once per run. No keyboard = 'none' (nothing is changed)."""
    global _late_action
    if _late_action is None:
        index = ask_choice(config, "The doctor did not join. What should the test do?",
                           [text for _, text in LATE_ACTIONS], default=len(LATE_ACTIONS) - 1)
        _late_action = LATE_ACTIONS[index][0]
        print(f"Chosen: {LATE_ACTIONS[index][1]}")
    return _late_action


def allow_new_cancel(config):
    """One cancellation per run. A second one only if you type yes."""
    global _cancels_this_run
    if _cancels_this_run >= 1 and not _ask_yes(
            config, "A booking was already cancelled in this run. Cancel ANOTHER one?"):
        pytest.exit("SAFETY STOP: a second cancellation in the same run was not approved. "
                    "Nothing else was cancelled.", returncode=3)
    _cancels_this_run += 1