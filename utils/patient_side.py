"""Patient app steps used by the doctor-app tests (same phone, same Appium session).
Uses the patient app's existing page objects (search, profile, Booking Summary, pop-up, payment) with the
doctor-app account's patient-side name (PATIENT_APP_DOCTOR_NAME) instead of test_data.DOCTOR_NAME.

Asked at the start of a run (with -s; nobody at the keyboard = the first choice):
  - where:   13-b Hospital (Pay at Clinic, nothing paid) or Video Consultation (paid from Marham Wallet)
  - for whom: Self or a family member (utils.safety.choose_patient)

Bookings card text (content-desc), Inspector 22 Oct 2026:
  "AWAITING CONFIRMATION, PAID, <icon>, TODAY, 22, 02:10 PM, <icon>, Dr. Momina Testing, Video Consultation,
   <icon>, Patient Name: Tooba, <icon>, Waiting for doctor confirmation."
  "SCHEDULED, PAY AT CLINIC, <icon>, TODAY, 22, 02:05 PM, <icon>, Dr. Momina Testing, 13-b Hospital, ..."
"""
import re
import time
import xml.etree.ElementTree as ET

import allure
from selenium.common.exceptions import StaleElementReferenceException

from doctor_test_data import DOCTOR_LOCATIONS, PATIENT_APP_DOCTOR_NAME, VIDEO
from pages.base_page import BasePage
from pages.bookings_page import BookingsPage
from pages.confirmation_page import ConfirmationPage
from pages.doctor_appointments_page import clean
from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.login_page import LoginPage
from pages.payment_page import PaymentPage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from test_data import TEST_PATIENT_NAME
from utils.doctor_app import to_patient_app
from utils.doctor_safety import doctor_stop
from utils.safety import allow_new_booking, ask_choice, choose_patient

_place = None


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def choose_place(config):
    """Asked once per run: which of the doctor's locations to book. No keyboard = the first one."""
    global _place
    if _place is None:
        names = list(DOCTOR_LOCATIONS)
        labels = [f"{n} - Rs. {DOCTOR_LOCATIONS[n]} paid NOW from Marham Wallet" if n == VIDEO
                  else f"{n} - Rs. {DOCTOR_LOCATIONS[n]}, Pay at Clinic (nothing paid now)" for n in names]
        _place = names[ask_choice(config, "Which booking should the test make with "
                                          f"{PATIENT_APP_DOCTOR_NAME}?", labels, default=0)]
        print(f"Booking at: {_place}")
    return _place


class Slot:
    """The booked slot: '22 Oct' + '02:05 PM' (Booking Summary) -> 'Oct 22' for the doctor app."""

    def __init__(self, date_text, time_text, place, patient):
        self.date_text, self.time = date_text.strip(), time_text.strip()
        self.place, self.patient = place, patient
        day, month = self.date_text.split()[:2]
        self.day = int(day)
        self.month_day = f"{month} {self.day}"            # Oct 22

    @property
    def is_video(self):
        return self.place == VIDEO

    def label(self):
        return f"{self.month_day}, {self.time}, {self.place}, for {self.patient}"


def _steady(action, *args, tries=5):
    """The profile's cards slide by themselves, so an element found a moment ago can be gone
    ('stale element'). Try the action again (max 5 times) instead of failing at once."""
    for attempt in range(tries):
        try:
            return action(*args)
        except StaleElementReferenceException:
            if attempt == tries - 1:
                raise
            time.sleep(1)


def book_visit(driver, config):
    """Patient app: book the test doctor at the chosen place, first free slot, for the chosen patient.
    Clinic = Pay at Clinic -> "Physical Appointment Request Received!".
    Video = paid from Marham Wallet -> "Video Consultation Request Received!" (Pending Confirmation). Stops the run (nothing booked) if the
    profile or the pop-up shows anything else."""
    place = choose_place(config)
    patient = choose_patient(config)
    fee = DOCTOR_LOCATIONS[place]

    to_patient_app(driver)
    driver.update_settings({"waitForIdleTimeout": 10000})   # patient app: wait for screens to settle (Appium default)
    try:
        return _book(driver, config, place, patient, fee)
    finally:
        driver.update_settings({"waitForIdleTimeout": 0})   # doctor app keeps animating: do not wait for idle


def _book(driver, config, place, patient, fee):
    home = HomePage(driver)
    assert home.is_loaded(), "Patient app home did not load"
    BasePage(driver).dismiss_popups()
    LoginPage(driver).ensure_logged_in()

    home.open_search()
    search = SearchPage(driver)
    search.search(PATIENT_APP_DOCTOR_NAME)
    assert search.has_result(PATIENT_APP_DOCTOR_NAME), f"{PATIENT_APP_DOCTOR_NAME} not in the search results"
    search.open_result(PATIENT_APP_DOCTOR_NAME)

    profile = DoctorProfilePage(driver)
    if not profile.has_text(PATIENT_APP_DOCTOR_NAME, timeout=profile.TIMEOUT):
        doctor_stop(f"opened profile does not show the test doctor '{PATIENT_APP_DOCTOR_NAME}'")
    _steady(profile.show_card, place)
    _steady(profile.show_card, place)                  # cards slide by themselves: bring it back before reading
    shown_fee = _steady(profile.clinic_fee)
    _note(shown_fee, f"{place} card fee (patient app)")
    assert _steady(profile.card_shows_fee, fee), (
        f"Patient app shows '{shown_fee}' for {place}; the doctor app (Manage Locations) says PKR {fee}")

    summary = SlotPage(driver)
    for _ in range(3):                                 # cards slide by themselves: retry if the wrong one opened
        _steady(profile._book_on_card, place)
        assert summary.is_open(), "Booking Summary did not open"
        if summary.has_text(place, timeout=5) or summary.shows(place):
            break
        summary.back()
    else:
        doctor_stop(f"Booking Summary does not show '{place}' after 3 tries")
    assert summary.slots_loaded(), "No time slots shown"

    date_text, time_text = summary.pick_first_free_slot()
    slot = Slot(date_text, time_text, place, patient)
    summary.select_patient(patient)
    _note(f"{slot.label()}; Total Amount {summary.total_amount()}", "chosen slot")

    summary.tap_book()
    assert summary.popup_open(), "Appointment Details pop-up did not open"
    for what, value in (("doctor", PATIENT_APP_DOCTOR_NAME), ("patient", patient), ("time", slot.time)):
        if not summary.popup_has(value):
            doctor_stop(f"Appointment Details pop-up does not show the {what} '{value}'")

    allow_new_booking(config)                          # 1 booking per run; asks before a 2nd
    summary.confirm_popup()
    _note(f"Booking created: {PATIENT_APP_DOCTOR_NAME}, {slot.label()}", "booking")
    print(f"\nBOOKING: {PATIENT_APP_DOCTOR_NAME}, {slot.label()}")
    if slot.is_video:
        _pay_with_wallet(driver, fee, slot)
    else:
        confirmation = ConfirmationPage(driver)
        assert confirmation.is_open(), "No 'Physical Appointment Request Received!' screen"
        for expected in (slot.time, place, "Pay at Clinic", "Pending Confirmation"):
            assert confirmation.has_text(expected), f"'{expected}' missing on the Request Received screen"
    return slot


def _pay_with_wallet(driver, fee, slot):
    payment = PaymentPage(driver)
    assert payment.is_open(), "Payment screen did not open"
    assert payment.shows_amount(fee), f"Total Payable Amount is not Rs. {fee}"
    balance = payment.wallet_balance()
    _note(f"Wallet balance before paying: Rs. {balance}", "wallet")
    assert balance >= int(fee), f"Wallet balance Rs. {balance} is lower than the fee Rs. {fee}"
    payment.turn_on_wallet()
    assert payment.shows_amount(0), "Total Payable is not Rs. 0 after turning the wallet on"
    payment.pay_with_wallet()
    _note(f"Paid Rs. {fee} from Marham Wallet for {slot.label()}", "payment")
    # This doctor confirms bookings himself, so the app shows "Video Consultation Request Received!"
    # (not "Consultation Confirmed!" as for a doctor without confirmation).
    received = ConfirmationPage(driver)
    assert received.is_open(), "No 'Video Consultation Request Received!' screen after Pay with Wallet"
    for expected in (PATIENT_APP_DOCTOR_NAME, VIDEO, slot.time, f"Rs. {fee}", "Paid", "Pending Confirmation"):
        assert received.has_text(expected), f"'{expected}' missing on the Request Received screen"


def booking_card(driver, slot, max_swipes=8):
    """Patient app > Bookings: the content-desc of this slot's card (doctor, place, day, time, patient), or ''."""
    to_patient_app(driver)
    bookings = BookingsPage(driver)
    assert bookings.open(), "Patient app Bookings did not open"
    wanted = re.compile(rf", {slot.day}, {re.escape(slot.time)},")
    for _ in range(max_swipes):
        root = ET.fromstring(driver.page_source.encode("utf-8"))
        for n in root.iter():
            desc = clean(n.get("content-desc"))
            for_patient = slot.patient == TEST_PATIENT_NAME or f"Patient Name: {slot.patient}" in desc
            if PATIENT_APP_DOCTOR_NAME in desc and slot.place in desc and wanted.search(desc) and for_patient:
                return desc
        if not bookings._scroll("down"):
            break
    return ""