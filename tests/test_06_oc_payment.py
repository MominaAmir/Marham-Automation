"""REAL booking: Video Consultation with the test doctor, paid from Marham Wallet.
Runs only when ALLOW_OC_PAYMENT = True in test_data.py. Retried at most once. One booking per run:
if the retry tries to book again, you must type yes in PowerShell."""
import allure
import pytest

from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.login_page import LoginPage
from pages.payment_page import PaymentPage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from test_data import DOCTOR_NAME, OC_FEE
from utils.safety import (allow_new_booking, check_popup_before_booking, check_profile_is_test_doctor,
                          choose_patient, require_oc_payment_allowed)
from utils.steps import step


def _note(text, name):
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


@pytest.mark.oc_payment
@pytest.mark.flaky(reruns=1, reruns_delay=5)   # max 1 retry; a 2nd booking still needs your "yes"
@allure.title("OC-PAY: book a video consultation with the test doctor and pay with Marham Wallet")
def test_oc_book_and_pay_with_wallet(driver, request):
    require_oc_payment_allowed()      # skipped while ALLOW_OC_PAYMENT = False
    patient = choose_patient(request.config)   # Self or a family member (asked once per run)
    home = HomePage(driver)
    summary = SlotPage(driver)

    with step("OCP-01"):
        assert home.is_loaded(), "Home screen did not load"
        LoginPage(driver).ensure_logged_in()
        home.open_search()
        search = SearchPage(driver)
        search.search(DOCTOR_NAME)
        search.open_result(DOCTOR_NAME)
        profile = DoctorProfilePage(driver)
        check_profile_is_test_doctor(profile.name())   # wrong doctor = whole run stops
        profile.start_online_consultation()
        assert summary.is_open(), "Booking Summary did not open"

    with step("OCP-02"):
        date_text, time_text = summary.pick_first_free_slot()
        _note(f"{date_text} {time_text}", "chosen slot")
        summary.select_patient(patient)
        _note(patient, "booked for")
        total = summary.total_amount()
        assert OC_FEE in total, f"Total Amount is '{total}', expected {OC_FEE}"

    with step("OCP-03"):
        summary.tap_book()
        assert summary.popup_open(), "Appointment Details pop-up did not open"

    with step("OCP-04"):
        check_popup_before_booking(summary, time_text, patient)   # doctor, patient, fee, time - else stops, no booking

    payment = PaymentPage(driver)
    with step("OCP-05"):
        allow_new_booking(request.config)                # 1 per run; asks before a 2nd
        summary.confirm_popup()
        _note(f"Booking created: {DOCTOR_NAME}, {date_text} {time_text}", "booking")
        assert payment.is_open(), "Payment screen did not open"
        assert payment.shows_amount(OC_FEE), f"Total Payable Amount is not Rs. {OC_FEE}"

    with step("OCP-06"):
        balance = payment.wallet_balance()
        _note(f"Wallet balance before paying: Rs. {balance}", "wallet")
        assert balance >= int(OC_FEE), f"Wallet balance Rs. {balance} is lower than the fee Rs. {OC_FEE}"
        payment.turn_on_wallet()
        assert payment.shows_amount(0), "Total Payable is not Rs. 0 after turning the wallet on"
        assert payment.is_visible(payment.PAY_WITH_WALLET, timeout=10), "No 'Pay with Wallet' button"

    with step("OCP-07"):
        payment.pay_with_wallet()
        assert payment.confirmed(), "No 'Consultation Confirmed!' screen after Pay with Wallet"
        short_name = DOCTOR_NAME.split("(")[0].strip()          # the name wraps onto 2 lines here
        for expected in (short_name, "Video Consultation", time_text, f"Rs. {OC_FEE}", "Paid"):
            assert payment.has_text(expected), f"'{expected}' missing on the Consultation Confirmed screen"

    with step("OCP-08"):
        assert payment.open_receipt(), "Receipt does not say 'Payment Successful'"
        for expected in (patient, "WALLET", "Paid", f"Rs. {OC_FEE}"):
            assert payment.has_text(expected), f"'{expected}' missing on the Transaction Receipt"
        booking_id = payment.booking_id()
        _note(f"Booking ID {booking_id} | {patient} | {DOCTOR_NAME} | {date_text} {time_text} | Rs. {OC_FEE} | WALLET",
              "booking id")
        print(f"\nPAID BOOKING: ID {booking_id}, {patient}, {date_text} {time_text}")