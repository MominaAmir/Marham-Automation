import allure
import pytest

from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from test_data import DOCTOR_NAME, TEST_PATIENT_NAME
from utils.app import restart_app
from utils.safety import check_profile_is_test_doctor
from utils.steps import step


def _open_oc_summary(driver):
    HomePage(driver).open_search()
    search = SearchPage(driver)
    search.search(DOCTOR_NAME)
    search.open_result(DOCTOR_NAME)
    profile = DoctorProfilePage(driver)
    check_profile_is_test_doctor(profile.name())   # wrong doctor = whole run stops
    profile.start_online_consultation()
    summary = SlotPage(driver)
    assert summary.is_open(), "Booking Summary did not open"
    return summary


@pytest.mark.negative
@allure.title("NEG-01: Book Appointment is hidden until a time slot AND a patient are chosen")
def test_book_hidden_until_slot_and_patient(driver):
    with step("NEG-01"):
        summary = _open_oc_summary(driver)
        assert not summary.final_book_button_shown(), "Book Appointment is shown before a slot is chosen"
        summary.pick_first_free_slot()
        assert not summary.final_book_button_shown(), "Book Appointment is shown before a patient is chosen"
        summary.select_patient(TEST_PATIENT_NAME)
        assert summary.final_book_button_shown(), "Book Appointment did not appear after slot + patient"
        # Not tapped: nothing is booked.

@pytest.mark.negative
@allure.title("NEG-02: app recovers after being killed mid-booking")
def test_relaunch_mid_flow(driver):
    with step("NEG-02"):
        _open_oc_summary(driver)
        restart_app(driver)
        home = HomePage(driver)
        assert home.is_loaded(), "Home did not load after relaunch"
        assert not home.is_logged_out(), "Logged out after relaunch"
        assert not home.has_error()