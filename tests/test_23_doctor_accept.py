"""Doctor app - accept a pending appointment, end to end on ONE phone.     pytest -m doctor_accept -s
Asks first: make a NEW booking, or use one ALREADY waiting in Pending Confirmations (nothing booked or paid).
For a new booking it asks where (13-b Hospital, Pay at Clinic / Video Consultation, paid from Marham Wallet)
and for whom (Self or a family member). Then:
1. Patient app books the test doctor (first free slot).
2. Doctor app: the booking waits in Pending Confirmations -> Accept.
3. Doctor app Appointments and patient app Bookings both show it SCHEDULED.
Creates ONE real (test) booking per run and leaves it accepted. Never taps Reschedule. Never retried."""
import time

import allure
import pytest

from doctor_test_data import ACCEPT_MESSAGE
from pages.doctor_appointments_page import DoctorAppointmentsPage
from pages.doctor_home_page import DoctorHomePage
from pages.doctor_pending_page import PendingConfirmationsPage
from test_data import TEST_PATIENT_NAME
from utils.doctor_app import to_doctor_app
from utils.doctor_safety import check_doctor
from utils.patient_side import Slot, book_visit, booking_card
from utils.safety import ask_choice
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_accept]


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _shot(driver, name):
    allure.attach(driver.get_screenshot_as_png(), name=name, attachment_type=allure.attachment_type.PNG)


def _open_pending(driver):
    """Doctor app, freshly started: test doctor check, tile count, Pending Confirmations opened."""
    to_doctor_app(driver)
    home, pending = DoctorHomePage(driver), PendingConfirmationsPage(driver)
    assert home.is_loaded(), "Doctor home ('Overview') did not load - is the test doctor logged in?"
    check_doctor(home.doctor_name())
    count = pending.tile_count()
    assert pending.open(), "Pending Confirmations did not open from the Home tile"
    return pending, count


def _waiting_booking(driver, config):
    """Use a booking that already waits in Pending Confirmations (asks which one if there are several)."""
    pending, _count = _open_pending(driver)
    cards = pending.cards()
    assert cards, "Nothing is waiting in Pending Confirmations: choose 'Make a NEW booking' instead"
    card = cards[0] if len(cards) == 1 else cards[
        ask_choice(config, "Which waiting booking should the doctor accept?", [c.label() for c in cards])]
    month, day = card.month_day.split()
    slot = Slot(f"{day} {month}", card.time, card.location, card.booked_for or TEST_PATIENT_NAME)
    print(f"Using the waiting booking: {slot.label()}")
    return slot


@pytest.mark.flaky(reruns=0)          # never retried: a retry would book a second appointment
@allure.title("DACC: patient books (clinic or video, Self or family) -> doctor accepts -> both apps show SCHEDULED")
def test_doctor_accepts_booking(driver, request):
    with step("DACC-01"):
        new = ask_choice(request.config, "Make a NEW booking, or use one ALREADY waiting in Pending Confirmations?",
                         ["Make a NEW booking from the patient app",
                          "Use a booking that is already waiting (nothing is booked or paid)"]) == 0
        slot = book_visit(driver, request.config) if new else _waiting_booking(driver, request.config)
        _note(f"{'new booking' if new else 'already waiting'}: {slot.label()}", "booking used")

    with step("DACC-02"):
        desc = booking_card(driver, slot)
        _note(desc or "not found", "patient Bookings card (before accept)")
        assert desc, f"Booking {slot.label()} not found in the patient app's Bookings"
        assert desc.startswith("AWAITING CONFIRMATION"), f"Booking is not AWAITING CONFIRMATION: {desc}"
        assert "Waiting for doctor confirmation" in desc, f"'Waiting for doctor confirmation.' missing: {desc}"

    with step("DACC-03"):
        pending, count_before = _open_pending(driver)
        cards = pending.cards()
        _note("\n".join(c.label() for c in cards) or "no cards", "pending cards")
        _note(count_before, "Home tile count before accept")
        card = next((c for c in cards if c.is_slot(slot.month_day, slot.time) and c.location == slot.place), None)
        assert card, f"The new booking ({slot.label()}) is not in Pending Confirmations:\n" + \
                     "\n".join(c.label() for c in cards)
        assert card.buttons == ["Accept", "Reschedule"], f"Buttons on the pending card: {card.buttons}"
        if slot.patient != TEST_PATIENT_NAME:            # family member: the doctor must see who it is for
            assert card.booked_for == slot.patient, \
                f"Card says 'Booked for {card.booked_for or '-'}', the booking was for {slot.patient}"
        assert count_before is None or count_before == len(cards), \
            f"Home tile says {count_before} pending, the screen lists {len(cards)}"

    with step("DACC-04"):
        new_texts = pending.accept(card)                # the ONLY tap that changes anything in the doctor app
        _shot(driver, "after Accept")
        _note(new_texts or "nothing new", "texts after Accept")
        print(f"\nACCEPTED: {card.label()}  -> app said: {new_texts}")
        assert any(ACCEPT_MESSAGE in t for t in new_texts), f"No '{ACCEPT_MESSAGE}' message after Accept: {new_texts}"
        time.sleep(2)
        assert pending.find(slot.month_day, slot.time) is None, "Card is still in Pending Confirmations after Accept"
        pending, count_after = _open_pending(driver)    # fresh start: the list and the tile come from the server
        assert pending.find(slot.month_day, slot.time) is None, "Card is back in Pending Confirmations after a restart"
        _note(count_after, "Home tile count after accept")
        if count_before is not None:
            assert (count_after or 0) == count_before - 1, f"Home tile went from {count_before} to {count_after}"

    with step("DACC-05"):
        to_doctor_app(driver)
        page = DoctorAppointmentsPage(driver)
        assert page.open(), "Appointments screen did not open"
        page.open_tab("Upcoming")
        found = [c for c in page.cards() if c.date.startswith(f"{slot.month_day},") and c.time == slot.time
                 and c.location == slot.place]
        _note("\n".join(c.label() for c in found) or "not found", "Appointments card")
        assert found, f"Accepted booking {slot.label()} not in the doctor's Appointments list"
        assert found[0].status.startswith("SCHEDULED"), f"Doctor's card is not SCHEDULED: {found[0].label()}"

    with step("DACC-06"):
        desc = booking_card(driver, slot)
        expected = "SCHEDULED, PAID" if slot.is_video else "SCHEDULED, PAY AT CLINIC"
        _note(desc or "not found", "patient Bookings card (after accept)")
        assert desc, f"Booking {slot.label()} not found in the patient app's Bookings after accept"
        assert desc.startswith(expected), f"Patient card is not '{expected}': {desc}"
        assert "Waiting for doctor confirmation" not in desc, f"Still says 'Waiting for doctor confirmation': {desc}"
        print(f"PATIENT SEES: {desc}")