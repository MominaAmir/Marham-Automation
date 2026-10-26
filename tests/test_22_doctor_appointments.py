"""Doctor app - Appointments tab, READ-ONLY.                 pytest -m doctor_appointments
Opens the tabs, reads every card, opens one appointment with 'View Detail' and goes back.
Never taps Start Session, Chat, Showed Up, Not Showed Up, Contact patient or the chat switch."""
import datetime

import allure
import pytest

from pages.doctor_appointments_page import AppointmentDetailsPage, DoctorAppointmentsPage
from pages.doctor_home_page import DoctorHomePage
from utils.doctor_safety import check_doctor
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_appointments]

# Buttons by time (seen in the app, 21-22 Oct):
# - always on a SCHEDULED card: View Detail (+ Chat on video cards)
# - on the appointment DAY: Start Session (video card / details)
# - once the appointment TIME has passed: Showed Up / Not Showed Up (clinic card),
#   Mark Showed Up / Mark Not Showed Up (details). Before that time they are not shown.
CARD_ALWAYS = {True: ("View Detail", "Chat"), False: ("View Detail",)}
CARD_ON_DAY = {True: ("Start Session",), False: ()}
CARD_AFTER_TIME = {True: (), False: ("Showed Up", "Not Showed Up")}
DETAIL_ALWAYS = ("Chat with Patient", "Previous Prescriptions", "Contact patient")
DETAIL_ON_DAY = {True: ("Start Session",), False: ()}
DETAIL_AFTER_TIME = ("Mark Showed Up", "Mark Not Showed Up")


def _device_now(driver):
    return datetime.datetime.strptime(driver.get_device_time("YYYY-MM-DD HH:mm"), "%Y-%m-%d %H:%M")


def _when(card):
    return datetime.datetime.strptime(f"{card.date} {card.time}", "%b %d, %Y %I:%M %p")


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _listing(cards):
    return "\n".join(c.label() for c in cards) or "no appointments"


@allure.title("DAPT: Appointments tabs, cards and one appointment's details (read-only)")
def test_doctor_appointments_read_only(driver):
    home, page, details = DoctorHomePage(driver), DoctorAppointmentsPage(driver), AppointmentDetailsPage(driver)

    with step("DAPT-01"):
        assert home.is_loaded(), "Doctor home ('Overview') did not load - is the test doctor logged in?"
        check_doctor(home.doctor_name())
        assert page.open(), "Appointments screen did not open (no cards and no 'No appointments found')"
        for name in page.TABS:
            assert page.tab(name) is not None, f"Tab '{name}' missing"
        shown = page.date_range_text()
        _note(shown, "date range")
        assert "Showing" in shown, f"Date range box does not say 'Showing ...': {shown}"

    with step("DAPT-02"):
        page.open_tab("Upcoming")
        cards = page.cards()
        badge = page.tab_count("Upcoming")
        _note(_listing(cards), "Upcoming cards")
        _note("\n".join(c.desc for c in cards), "raw card text")
        print(f"\nUPCOMING ({len(cards)} cards, tab shows {badge}):\n{_listing(cards)}")
        if not cards:
            assert page.is_visible(page.EMPTY, timeout=3), "No cards and no 'No appointments found'"
        for c in cards:
            assert c.status and c.patient and c.date and c.time and c.location, f"Card with missing data: {c.desc}"
        if badge is not None:
            assert len(cards) == badge, f"Upcoming tab shows {badge}, but {len(cards)} cards were found"

    with step("DAPT-04"):
        now = _device_now(driver)
        problems, seen = [], []
        for c in cards:
            if c.status != "SCHEDULED":
                continue
            on_day, started = _when(c).date() == now.date(), now >= _when(c)
            expected = (CARD_ALWAYS[c.is_video] + (CARD_ON_DAY[c.is_video] if on_day else ())
                        + (CARD_AFTER_TIME[c.is_video] if started else ()))
            missing = [b for b in expected if b not in c.buttons]
            seen.append(f"{'started' if started else 'today' if on_day else 'later'}: {c.label()}")
            if missing:
                problems.append(f"{c.label()} -> missing {missing}")
        _note(f"phone time {now:%d %b %H:%M}\n" + "\n".join(seen), "buttons per card")
        assert not problems, f"Cards without their buttons (phone time {now:%d %b %H:%M}):\n" + "\n".join(problems)

    with step("DAPT-05"):
        if not cards:
            pytest.skip("No upcoming appointment to open")
        card = next((c for c in cards if c.is_video and c.status == "SCHEDULED"), cards[0])
        _note(card.label(), "appointment opened")
        page.open_details(card)                          # 'View Detail' - nothing else is tapped
        assert details.is_open(), "'Appointment Details' did not open"
        texts = details.texts()
        expected = [card.patient, card.status, card.date, card.time] + ([card.location] if card.is_video else [])
        for value in expected:
            assert value in texts, f"'{value}' (from the card) missing on Appointment Details"
        buttons = details.buttons()
        _note(f"buttons: {buttons}\nPatient Chat Access on: {details.chat_access_on()}", "details buttons")
        now = _device_now(driver)
        on_day, started = _when(card).date() == now.date(), now >= _when(card)
        expected = (DETAIL_ALWAYS + (DETAIL_ON_DAY[card.is_video] if on_day else ())
                    + (DETAIL_AFTER_TIME if started else ()))
        missing = [b for b in expected if b not in buttons]
        assert not missing, (f"Buttons missing on Appointment Details: {missing} (shown: {buttons}; "
                             f"appointment {card.date} {card.time}, phone time {now:%d %b %H:%M})")

    with step("DAPT-06"):
        payment = details.payment_texts()
        _note(" | ".join(payment) or "nothing below 'Payment Details'", "payment details")
        print(f"PAYMENT DETAILS: {' | '.join(payment)}")
        assert payment, "'Payment Details' not found or empty"

    with step("DAPT-07"):
        details.go_back()
        assert page.is_visible(page.TITLE, timeout=10), "Did not go back to Appointments"
        assert page.tab("Upcoming") is not None, "Tabs missing after going back"

    with step("DAPT-08"):
        for name in ("Completed", "Others"):
            page.open_tab(name)
            tab_cards = page.cards()
            _note(_listing(tab_cards), f"{name} cards")
            print(f"{name.upper()} ({len(tab_cards)}): {_listing(tab_cards)}")
            if not tab_cards:
                assert page.is_visible(page.EMPTY, timeout=3), f"{name}: no cards and no 'No appointments found'"
            for c in tab_cards:
                assert c.patient and c.date and c.time, f"{name}: card with missing data: {c.desc}"
        page.open_tab("Upcoming")