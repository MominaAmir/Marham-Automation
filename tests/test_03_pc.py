"""REAL booking: in-clinic (PC) appointment with the test doctor at the test hospital. Pay at Clinic.
Runs only when ALLOW_PC_BOOKING = True in test_data.py. Retried at most once. One booking per run:
if anything tries to book again, you must type yes in PowerShell."""
import allure
import pytest

from pages.confirmation_page import ConfirmationPage
from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from test_data import DOCTOR_NAME, HOSPITAL, PC_FEE
from utils.safety import (allow_new_booking, check_popup_before_booking, check_profile_is_test_doctor,
                          choose_patient, require_pc_booking_allowed, stop_run)
from utils.steps import step


def _note(text, name):
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


@pytest.mark.pc
@pytest.mark.flaky(reruns=1, reruns_delay=5)   # max 1 retry; a 2nd booking still needs your "yes"
@allure.title("PC: book an in-clinic appointment with the test doctor at the test hospital (Pay at Clinic)")
def test_pc_book_in_clinic(driver, request):
    require_pc_booking_allowed()                 # skipped while ALLOW_PC_BOOKING = False
    patient = choose_patient(request.config)     # Self or a family member (asked once per run)
    home = HomePage(driver)
    profile = DoctorProfilePage(driver)
    summary = SlotPage(driver)

    with step("PC-01"):
        assert home.is_loaded(), "Home screen did not load"
        assert not home.has_error(), "Home screen shows an error message"
        LoginPage(driver).ensure_logged_in()

    with step("PC-02"):
        home.open_search()
        search = SearchPage(driver)
        search.search(DOCTOR_NAME)
        search.open_result(DOCTOR_NAME)
        check_profile_is_test_doctor(profile.name())   # wrong doctor = whole run stops

    with step("PC-03"):
        profile.select_clinic(HOSPITAL)                 # swipe the cards to the test hospital
        assert profile.clinic_address(), "Hospital address not shown"
        profile.select_clinic(HOSPITAL)                 # cards slide by themselves: bring it back before reading
        assert profile.card_shows_fee(PC_FEE), f"Hospital card does not show Rs. {PC_FEE}"

    with step("PC-04"):
        for _ in range(3):                              # cards slide by themselves: retry if the wrong one opened
            profile.book_visit(HOSPITAL)
            assert summary.is_open(), "Booking Summary did not open"
            if summary.has_text(HOSPITAL, timeout=5):   # the pop-up does not show the hospital, so check here
                break
            summary.back()                              # wrong card's summary: go back to the profile, try again
        else:
            stop_run(f"Booking Summary does not show the test hospital '{HOSPITAL}' after 3 tries")
        assert summary.slots_loaded(), "No time slots shown"

    with step("PC-05"):
        date_text, time_text = summary.pick_first_free_slot()
        _note(f"{date_text} {time_text}", "chosen slot")
        summary.select_patient(patient)
        _note(patient, "booked for")
        assert summary.shows("Hospital Discount"), "Hospital Discount line missing in Payment Summary"
        total = summary.total_amount()
        assert total == f"Rs. {PC_FEE}", f"Total Amount is '{total}', expected Rs. {PC_FEE}"

    with step("PC-06"):
        summary.tap_book()
        assert summary.popup_open(), "Appointment Details pop-up did not open"

    with step("PC-07"):
        check_popup_before_booking(summary, time_text, patient, fee=PC_FEE)   # else stops, no booking

    confirmation = ConfirmationPage(driver)
    with step("PC-08"):
        allow_new_booking(request.config)            # 1 per run; asks before a 2nd
        summary.confirm_popup()
        _note(f"PC booking created: {DOCTOR_NAME}, {HOSPITAL}, {date_text} {time_text}", "booking")
        assert confirmation.is_open(), "No 'Physical Appointment Request Received!' screen"

    with step("PC-09"):
        short_name = DOCTOR_NAME.split("(")[0].strip()          # the name wraps onto 2 lines here
        for expected in (short_name, time_text, HOSPITAL, "Pay at Clinic", "Pending Confirmation"):
            assert confirmation.has_text(expected), f"'{expected}' missing on the Request Received screen"
        print(f"\nPC BOOKING: {patient}, {HOSPITAL}, {date_text} {time_text}, Pay at Clinic, Pending Confirmation")