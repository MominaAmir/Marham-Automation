"""Doctor did not join a video booking (OC). Run it when 'Cancel & Refund' shows on a test-doctor
video booking (15 minutes after its time):   pytest -m late_oc -s
It checks the late screens, then ASKS what to do:
  1) Cancel & Refund   2) Wait More for 5 Minutes   3) Reschedule - check only   4) Nothing
No keyboard = 4. If there is no late booking, the test is skipped. Never retried."""
import time

import allure
import pytest

from pages.bookings_page import (AppointmentDetailsPage, BookingsPage, CancelRefundPage, ReschedulePage,
                                 SHORT_NAME)
from pages.home_page import HomePage
from pages.login_page import LoginPage
from test_data import CANCEL_REASON, DOCTOR_NAME, OC_FEE
from utils.app import restart_app
from utils.safety import allow_new_cancel, ask_choice, choose_late_action, stop_run
from utils.steps import step


def _note(text, name):
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


@pytest.mark.late_oc
@pytest.mark.flaky(reruns=0)      # never retried: a retry could act on a different booking
@allure.title("Late doctor (OC): check the screens, then Cancel & Refund / Wait More / Reschedule as you choose")
def test_late_doctor_options(driver, request):
    home = HomePage(driver)
    bookings = BookingsPage(driver)
    details = AppointmentDetailsPage(driver)

    # ---------- find a late booking (no late booking = skip, nothing is touched) ----------
    assert home.is_loaded(), "Home screen did not load"
    LoginPage(driver).ensure_logged_in()
    assert bookings.open(), "Bookings screen did not open"
    late = bookings.late_bookings()
    if not late:
        pytest.skip("No late test-doctor video booking. Run again when 'Cancel & Refund' shows on its card "
                    "(15 minutes after the slot time).")
    choice = 0 if len(late) == 1 else ask_choice(
        request.config, "More than one late booking. Which one should I test?", [b.label() for b in late])
    booking = late[choice]
    _note(booking.desc, "card text")

    with step("LATE-01"):
        for tab in bookings.TABS:
            assert bookings.has_text(tab), f"Tab '{tab}' missing on Bookings"
        for expected in ("SCHEDULED", "PAID", "Video Consultation", SHORT_NAME):
            assert expected in booking.desc, f"'{expected}' missing on the late card: {booking.desc}"
        assert booking.time, f"No date/time found on the late card: {booking.desc}"

    with step("LATE-02"):
        bookings.open_booking(booking, bookings.SCHEDULED_CARD)
        assert details.is_open(), "Appointment Details did not open"
        if not details.has_text(DOCTOR_NAME, timeout=8):          # full name, e.g. in the notice
            stop_run(f"Appointment Details does not show the test doctor '{DOCTOR_NAME}'")
        for expected in ("Video Consultation", "SCHEDULED", "PAID", booking.time,
                         "join your consultation", f"PKR {OC_FEE} is safe"):
            assert details.has_text(expected), f"'{expected}' missing on Appointment Details"

    with step("LATE-03"):
        for option in details.OPTIONS:
            assert details.shows(option), f"Option '{option}' missing"
        for expected in ("Payment Received", "Doctor Confirmed", "Doctor is Running Late",
                         "Consultation Fee", "Payment Status", "Total Paid"):
            assert details.shows(expected), f"'{expected}' missing on Appointment Details"
        assert details.shows_exact(f"Rs. {OC_FEE}"), f"Rs. {OC_FEE} missing in Payment Details"
        assert details.shows_exact("Paid"), "Payment Status is not 'Paid'"

    action = choose_late_action(request.config)
    _note(action, "your choice")
    if action == "cancel":
        _cancel_and_refund(driver, request, booking)
    elif action == "wait":
        _wait_more(details, booking)
    elif action == "reschedule":
        _check_reschedule(details)
    else:
        print("\nNothing changed: only the late-booking checks were run.")


def _cancel_and_refund(driver, request, booking):
    details = AppointmentDetailsPage(driver)
    page = CancelRefundPage(driver)
    bookings = BookingsPage(driver)

    with step("RF-01"):
        details.tap_label("Cancel & Refund")
        assert page.cancel_screen_open(), "'Cancel appointment' screen did not open"
        assert page.has_text("Tell us why you want to cancel"), "Cancel reason question missing"
        for reason in page.REASONS:
            assert page.has_text(reason), f"Reason '{reason}' missing"

    with step("RF-02"):
        page.confirm_cancel()                                    # no reason picked yet
        assert page.is_visible(page.PICK_REASON, timeout=5), "No 'Pick a reason' error without a reason"
        assert page.cancel_screen_open(), "Left the Cancel screen without a reason"

    with step("RF-03"):
        allow_new_cancel(request.config)                         # 1 per run; asks before a 2nd
        page.pick_reason(CANCEL_REASON)
        page.confirm_cancel()
        _note(f"Cancelled {booking.label()} - reason: {CANCEL_REASON}", "cancellation")
        assert page.refund_screen_open(), "Refund screen did not open after Confirm cancel"
        for expected in ("Refund amount", "Marham Wallet", "Refund to Marham Wallet", "Recommended"):
            assert page.has_text(expected), f"'{expected}' missing on the Refund screen"
        assert page.shows_exact(f"Rs. {OC_FEE}"), f"Refund amount is not Rs. {OC_FEE}"

    with step("RF-04"):
        page.request_refund()
        assert page.submitted(), "No 'Refund Request Submitted!' screen"
        for expected in ("Marham Wallet", "Total Amount", "Submitted", "24 business hours"):
            assert page.has_text(expected), f"'{expected}' missing on Refund Request Submitted"
        assert page.shows_exact(f"Rs. {OC_FEE}"), f"Refund is not Rs. {OC_FEE}"

    with step("RF-05"):
        page.back_to_appointments()
        assert bookings.is_visible(bookings.OPEN_CHECK, timeout=20), "Did not go back to Bookings"
        desc = bookings.card_desc(booking, bookings.CANCELLED_CARD)
        assert desc, f"Card {booking.label()} does not show CANCELLED"
        for expected in ("CANCELLED", "TO BE REFUNDED", "under review"):
            assert expected in desc, f"'{expected}' missing on the cancelled card: {desc}"

    with step("RF-06"):
        bookings.open_booking(booking, bookings.CANCELLED_CARD)
        assert details.is_open(), "Appointment Details did not open for the cancelled booking"
        for expected in ("CANCELLED", "TO BE REFUNDED", "refund request has been received",
                         "Appointment Cancelled", "Refund In Progress", "To Be Refunded", "Track your refund"):
            assert details.shows(expected), f"'{expected}' missing on the cancelled booking's details"

    with step("RF-07"):
        details.tap_label("Track your refund")
        assert page.refund_details_open(), "'Refund Details' did not open"
        for expected in ("Marham Wallet", f"PKR {OC_FEE}", "Requested", "Approved", "Processing", "Refunded",
                         "Destination", "Reference #"):
            assert page.has_text(expected), f"'{expected}' missing on Refund Details"
        reference = page.reference()
        _note(f"Refund reference #{reference} for {booking.label()}", "refund reference")
        print(f"\nREFUND REQUESTED: {booking.label()}, Rs. {OC_FEE}, reference #{reference}")

    with step("RF-08"):
        restart_app(driver)                                      # Home only updates after a reload
        home = HomePage(driver)
        assert home.is_loaded(), "Home screen did not load after restart"
        stale = home.has_text("View Options", timeout=5) and home.has_text(booking.time, timeout=2)
        assert not stale, f"Home still offers 'View Options' for the cancelled {booking.time} booking"


def _wait_more(details, booking):
    with step("WAIT-01"):
        before = details.visible_texts()
        details.tap_label("Wait More for 5 Minutes")
        time.sleep(5)
        after = details.visible_texts()
        allure.attach(details.driver.get_screenshot_as_png(), name="after Wait More",
                      attachment_type=allure.attachment_type.PNG)
        _note("\n".join(after), "screen after Wait More")
        print(f"\nAFTER 'Wait More for 5 Minutes' ({booking.label()}) the screen shows:\n  " + "\n  ".join(after))
        assert after, "Screen is empty after Wait More"
        if after == before:
            print("  (nothing on the screen changed after tapping Wait More)")


def _check_reschedule(details):
    page = ReschedulePage(details.driver)

    with step("RS-01"):
        details.tap_label("Reschedule")
        assert page.choice_open(), "'Same doctor' / 'Another doctor' choice did not open"
        assert page.has_text("Keep this doctor"), "'Same doctor' explanation missing"

    with step("RS-02"):
        assert page.open_same_doctor(), "Same doctor: Available Slots did not open"
        for expected in (SHORT_NAME, "Video Consultation", "Book Appointment"):
            assert page.has_text(expected), f"'{expected}' missing on the Reschedule screen"
        assert page.shows("Confirm reschedule"), "'Confirm reschedule' button missing"   # NOT tapped

    with step("RS-03"):
        date_text, early = page.slots_too_early()
        _note(f"First date {date_text}; slots earlier than now + 15 min: {early or 'none'}", "slot rule")
        assert not early, f"Slots less than 15 minutes ahead are offered on {date_text}: {early}"
        page.back()                                              # leaves without rescheduling
