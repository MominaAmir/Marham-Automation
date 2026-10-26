"""Bookings tab + the screens behind a late-doctor video booking:
Appointment Details, Cancel appointment, Refund, Refund Request Submitted!, Refund Details, Reschedule."""
import datetime
import re

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException

from pages.base_page import BasePage, text_contains
from pages.home_page import HomePage
from test_data import DOCTOR_NAME, FAMILY_MEMBERS, TEST_PATIENT_NAME

SHORT_NAME = DOCTOR_NAME.split("(")[0].strip()          # "Prof. Dr. Ehsan Bhatti" (cards cut the name short)
WHEN = re.compile(r"(TODAY|[A-Z]{3}), (\d{1,2}), (\d{1,2}:\d{2} [AP]M)")   # "TODAY, 16, 11:00 AM" in a card
TIME_SLOT = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("[0-9]{1,2}:[0-9]{2} [AP]M")')
DATE_CHIP = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("[0-9]{1,2} [A-Z][a-z]{2}")')


def exact(text):
    """Element whose text is exactly `text`."""
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{text}")')


def desc_starts(text):
    """Element whose content-desc starts with `text` (each booking card keeps all its text there)."""
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().descriptionStartsWith("{text}")')


def _inside(element, box):
    """True if the middle of `element` lies inside `box` (e.g. a button inside one card)."""
    e, b = element.rect, box.rect
    x, y = e["x"] + e["width"] / 2, e["y"] + e["height"] / 2
    return b["x"] <= x <= b["x"] + b["width"] and b["y"] <= y <= b["y"] + b["height"]


class Booking:
    """One appointment card, remembered by its date + time + patient (its status tags change)."""

    def __init__(self, desc):
        self.desc = desc
        found = WHEN.search(desc)
        self.when = found.group(0) if found else ""        # "TODAY, 16, 11:00 AM"
        self.time = found.group(3) if found else ""        # "11:00 AM"
        self.patient = next((p for p in [TEST_PATIENT_NAME] + list(FAMILY_MEMBERS) if p in desc), "")

    def label(self):
        return f"{self.when} - patient {self.patient or '?'}"

    def matches(self, desc):
        return bool(self.when) and self.when in desc and self.patient in desc


class BookingsPage(BasePage):
    TABS = ("Appointments", "Lab Tests", "Medicine Orders")
    OPEN_CHECK = exact("Medicine Orders")                 # "Bookings" alone is also the bottom tab's name
    ANY_CARD = text_contains("Patient Name")
    SCHEDULED_CARD = desc_starts("SCHEDULED, PAID")
    CANCELLED_CARD = desc_starts("CANCELLED")
    CARD_NAME = text_contains(SHORT_NAME)
    CANCEL_REFUND = exact("Cancel & Refund")

    def open(self):
        HomePage(self.driver).open_appointments()
        opened = self.is_visible(self.OPEN_CHECK, timeout=self.TIMEOUT)
        self.is_visible(self.ANY_CARD, timeout=15)        # wait for the list to load
        return opened

    # ---------- scrolling the list ----------
    def _scroll(self, direction, percent=0.6):
        size = self.driver.get_window_size()
        area = {"left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.45)}
        return self.driver.execute_script("mobile: scrollGesture",
                                          {**area, "direction": direction, "percent": percent})

    def scroll_to_top(self):
        for _ in range(10):
            if not self._scroll("up", 1.0):
                break

    # ---------- finding cards ----------
    def late_bookings(self, max_swipes=8):
        """Test-doctor video bookings whose card shows 'Cancel & Refund' (the doctor did not join)."""
        found = {}
        for _ in range(max_swipes):
            buttons = self.driver.find_elements(*self.CANCEL_REFUND)
            for card in self.driver.find_elements(*self.SCHEDULED_CARD):
                desc = card.get_attribute("content-desc") or ""
                if SHORT_NAME in desc and "Video Consultation" in desc and any(_inside(b, card) for b in buttons):
                    found.setdefault(desc, Booking(desc))
            if not self._scroll("down"):
                break
        self.scroll_to_top()
        return list(found.values())

    def card_desc(self, booking, card_locator, max_swipes=8):
        """The full text of this booking's card (searched from the top), or '' if not found."""
        self.scroll_to_top()
        for _ in range(max_swipes):
            for card in self.driver.find_elements(*card_locator):
                desc = card.get_attribute("content-desc") or ""
                if booking.matches(desc):
                    return desc
            if not self._scroll("down", 0.4):
                break
        return ""

    def open_booking(self, booking, card_locator, max_swipes=8):
        """Tap the doctor's name on this booking's card: opens its Appointment Details."""
        self.scroll_to_top()
        for _ in range(max_swipes):
            for card in self.driver.find_elements(*card_locator):
                if booking.matches(card.get_attribute("content-desc") or ""):
                    names = [n for n in self.driver.find_elements(*self.CARD_NAME) if _inside(n, card)]
                    if names:
                        names[0].click()
                        return
            if not self._scroll("down", 0.4):
                break
        raise AssertionError(f"Card {booking.label()} not found on the Bookings screen")


class LongScreen(BasePage):
    """Helpers for screens that need scrolling."""

    def shows(self, text):
        """True if `text` is anywhere on the screen (scrolls to find it)."""
        try:
            self.scroll_to_text(text)
            return True
        except TimeoutException:
            return False

    def shows_exact(self, text):
        """Like shows(), but the text must match exactly ('Rs. 3' must not match 'Rs. 30')."""
        return self.shows(text) and self.is_visible(exact(text), timeout=2)

    def tap_label(self, label):
        """Tap a button by its accessibility id or its exact text."""
        for locator in ((AppiumBy.ACCESSIBILITY_ID, label), exact(label)):
            if self.is_visible(locator, timeout=3):
                self.find(locator).click()
                return
        self.scroll_to_text(label)
        self.find(exact(label)).click()

    def visible_texts(self):
        return [e.text.strip() for e in self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                if e.text and e.text.strip()]


class AppointmentDetailsPage(LongScreen):
    TITLE = exact("Appointment Details")
    OPTIONS = ("Wait More for 5 Minutes", "Reschedule", "Cancel & Refund")

    def is_open(self):
        return self.is_visible(self.TITLE, timeout=self.TIMEOUT)


class CancelRefundPage(LongScreen):
    CANCEL_TITLE = exact("Cancel appointment")
    REASONS = ("Doctor was not available", "Doctor did not confirm", "Other")
    PICK_REASON = exact("Pick a reason")                     # red error when Confirm cancel is tapped too early
    REFUND_TITLE = text_contains("Choose refund method")
    REQUEST_REFUND = (AppiumBy.ACCESSIBILITY_ID, "Request Refund")
    SUBMITTED = text_contains("Refund Request Submitted")
    BACK_TO_APPOINTMENTS = exact("Back to Appointments")
    REFUND_DETAILS = exact("Refund Details")
    REFERENCE = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("[0-9]{4,}")')

    def cancel_screen_open(self):
        return self.is_visible(self.CANCEL_TITLE, timeout=self.TIMEOUT)

    def pick_reason(self, reason):
        self.find(text_contains(reason[:25])).click()

    def confirm_cancel(self):
        self.tap_label("Confirm cancel")

    def refund_screen_open(self):
        return self.is_visible(self.REFUND_TITLE, timeout=30)

    def request_refund(self):
        self.tap(self.REQUEST_REFUND)

    def submitted(self):
        return self.is_visible(self.SUBMITTED, timeout=30)

    def back_to_appointments(self):
        self.tap(self.BACK_TO_APPOINTMENTS)

    def refund_details_open(self):
        return self.is_visible(self.REFUND_DETAILS, timeout=self.TIMEOUT)

    def reference(self):
        return self.text_of(self.REFERENCE) if self.is_visible(self.REFERENCE, timeout=3) else ""


class ReschedulePage(LongScreen):
    SAME_DOCTOR = exact("Same doctor")
    ANOTHER_DOCTOR = exact("Another doctor")        # shows REAL doctors: the tests never tap it
    SLOTS_TITLE = text_contains("Available Slots")

    def choice_open(self):
        return self.is_visible(self.SAME_DOCTOR, timeout=self.TIMEOUT) and self.is_visible(self.ANOTHER_DOCTOR)

    def open_same_doctor(self):
        self.tap(self.SAME_DOCTOR)
        return self.is_visible(self.SLOTS_TITLE, timeout=self.TIMEOUT)

    def slots_too_early(self):
        """Slot rule: a slot must be at least 15 minutes after the phone's time.
        Taps the first date; if that date is today, returns every visible slot that breaks the rule."""
        self.scroll_to_text("Book Appointment")              # back up to the date chips
        chip = self.find(DATE_CHIP)
        chip_text = self.read(chip)
        chip.click()
        self.is_visible(TIME_SLOT, timeout=10)
        slots = [self.read(e) for e in self.driver.find_elements(*TIME_SLOT)]
        now = datetime.datetime.strptime(self.driver.get_device_time("YYYY-MM-DD HH:mm"), "%Y-%m-%d %H:%M")
        if datetime.datetime.strptime(f"{chip_text} {now.year}", "%d %b %Y").date() != now.date():
            return chip_text, []                     # first date is not today: nothing to check
        limit = now + datetime.timedelta(minutes=14)   # 15 min, minus 1 min for the time the test takes
        early = [s for s in slots
                 if datetime.datetime.combine(now.date(), datetime.datetime.strptime(s, "%I:%M %p").time()) < limit]
        return chip_text, early
