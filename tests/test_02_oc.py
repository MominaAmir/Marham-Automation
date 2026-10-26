import allure
import pytest

from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from test_data import DOCTOR_NAME, OC_FEE, TEST_PATIENT_NAME
from utils.safety import check_profile_is_test_doctor
from utils.steps import step


@pytest.mark.oc
@allure.title("OC: patient fills the Booking Summary for a video consultation (nothing is booked)")
def test_oc_booking_summary(driver):
    home = HomePage(driver)
    with step("OC-01"):
        assert home.is_loaded(), "Home screen did not load"
        assert not home.has_error(), "Home screen shows an error message"

    with step("OC-02"):
        LoginPage(driver).ensure_logged_in()

    search = SearchPage(driver)
    with step("OC-03"):
        home.open_search()
        search.search(DOCTOR_NAME)
        assert search.has_result(DOCTOR_NAME), f"{DOCTOR_NAME} not in search results"

    profile = DoctorProfilePage(driver)
    with step("OC-04"):
        search.open_result(DOCTOR_NAME)
        check_profile_is_test_doctor(profile.name())   # wrong doctor = whole run stops
        assert profile.has_online_option(), "No Video Consultation card"
        assert OC_FEE in profile.online_fee(), f"Video fee is {profile.online_fee()}, expected {OC_FEE}"

    summary = SlotPage(driver)
    with step("OC-05"):
        profile.start_online_consultation()
        assert summary.is_open(), "Booking Summary did not open"
        assert summary.slots_loaded(), "No time slots shown"

    with step("OC-06"):
        date_text, time_text = summary.pick_first_free_slot()
        allure.attach(f"{date_text} {time_text}", name="chosen slot",
                      attachment_type=allure.attachment_type.TEXT)
        assert date_text and time_text, "Could not read the chosen date / time"

    with step("OC-07"):
        summary.select_patient(TEST_PATIENT_NAME)

    with step("OC-08"):
        assert summary.shows(DOCTOR_NAME), "Test doctor's name missing on Booking Summary"
        assert summary.shows("Video Consultation"), "'Video Consultation' missing on Booking Summary"

    with step("OC-09"):
        total = summary.total_amount()
        assert OC_FEE in total, f"Total Amount is '{total}', expected {OC_FEE}"

    with step("OC-10"):
        assert summary.book_button_enabled(), "Final Book Appointment button missing or disabled"
        # Deliberately NOT tapped: on production we stop here, so nothing is booked.

    with step("OC-11"):
        summary.back()
        assert not summary.is_open(timeout=5), "Still on Booking Summary after Back"
        assert not home.has_error()