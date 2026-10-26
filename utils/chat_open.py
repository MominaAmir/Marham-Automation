"""Open the doctor <-> test patient chat in each app (shared by the chat tests).
Doctor app : fresh start -> doctor check -> Appointments -> first card with 'Chat' (Upcoming, then Completed).
Patient app: fresh start -> Bookings -> SCHEDULED card of the test doctor -> 'Chat with doctor'
(no SCHEDULED card: any card of the test doctor with 'Chat with doctor' - it is the same chat).
No such card at all -> the test is skipped."""
import allure
import pytest

from doctor_test_data import PATIENT_APP_DOCTOR_NAME
from pages.bookings_page import BookingsPage
from pages.chat_page import ChatPage, _root, chat_icon, open_doctor_chat
from pages.doctor_appointments_page import _tap_box
from pages.doctor_home_page import DoctorHomePage
from utils.doctor_app import to_doctor_app, to_patient_app
from utils.doctor_safety import check_doctor


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def doctor_chat(driver):
    to_doctor_app(driver)
    home = DoctorHomePage(driver)
    assert home.is_loaded(), "Doctor home ('Overview') did not load"
    check_doctor(home.doctor_name())
    card = open_doctor_chat(driver)
    if card is None:
        pytest.skip("No appointment with a 'Chat' button in Upcoming or Completed: book and accept one first "
                    "(pytest -m doctor_accept -s)")
    _note(card.label(), "chat opened from this card")
    chat = ChatPage(driver)
    assert chat.is_open(), f"Chat did not open from {card.label()}"
    return chat


def patient_chat(driver):
    driver.update_settings({"waitForIdleTimeout": 10000})
    try:
        to_patient_app(driver)
        bookings = BookingsPage(driver)
        assert bookings.open(), "Patient app Bookings did not open"
        desc, icon, other = None, None, (None, None)
        for _ in range(8):                         # SCHEDULED card first; else any card with 'Chat with doctor'
            root = _root(driver)
            desc, icon = chat_icon(root, PATIENT_APP_DOCTOR_NAME)
            if other[1] is None:
                other = chat_icon(root, PATIENT_APP_DOCTOR_NAME, status=None)
            if icon or not bookings._scroll("down"):
                break
        if not icon and other[1]:
            desc, icon = other                     # one chat per account: every card opens the same chat
            bookings.scroll_to_top()
            for _ in range(8):                     # bring that card back on screen to tap it
                desc, icon = chat_icon(_root(driver), PATIENT_APP_DOCTOR_NAME, status=None)
                if icon or not bookings._scroll("down"):
                    break
        if not icon:
            pytest.skip(f"No booking of {PATIENT_APP_DOCTOR_NAME} with 'Chat with doctor' in Bookings: "
                        "book and accept one first (pytest -m doctor_accept -s)")
        _note(desc, "patient chat opened from this card")
        _tap_box(driver, icon)
    finally:
        driver.update_settings({"waitForIdleTimeout": 0})
    chat = ChatPage(driver)
    assert chat.is_open(), "Patient chat did not open from the Bookings card"
    return chat