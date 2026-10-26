from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException

from pages.base_page import BasePage, text_contains
from test_data import DOCTOR_NAME, HOSPITAL_ADDRESS


def exact_text(text):
    """Locator for an element whose text is exactly `text`."""
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{text}")')


class DoctorProfilePage(BasePage):
    # The profile shows swipeable cards: one per hospital + one "Video Consultation".
    # Every card has its own "Consultation Fee" and "Book Appointment".
    VIDEO_CARD_TITLE = "Video Consultation"
    FEE_LABEL = text_contains("Consultation Fee")
    FEE_AMOUNT = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textStartsWith("Rs.")')
    BOOK_BTN = exact_text("Book Appointment")

    # ---------- doctor name (used by the safety check) ----------
    def name(self):
        try:
            return self.read(self.find(text_contains(DOCTOR_NAME), timeout=self.TIMEOUT))
        except TimeoutException:
            return "(test doctor's name is not on this screen)"

    # ---------- cards ----------
    def _on_screen(self, locator):
        """The first matching element that is really inside the screen (not on a hidden card)."""
        width = self.driver.get_window_size()["width"]
        for el in self.driver.find_elements(*locator):
            r = el.rect
            if el.is_displayed() and 0 <= r["x"] + r["width"] / 2 <= width:
                return el
        return None

    def _swipe_cards(self, direction):
        self.scroll_to_text("Consultation Fee")
        label = self._on_screen(self.FEE_LABEL) or self.find(self.FEE_LABEL)
        width = self.driver.get_window_size()["width"]
        self.driver.execute_script("mobile: swipeGesture", {
            "left": int(width * 0.1), "top": label.rect["y"], "width": int(width * 0.8),
            "height": max(label.rect["height"], 20), "direction": direction, "percent": 0.8})

    def show_card(self, title, max_swipes=4):
        """Swipe the cards left, then right, until the card called `title` is on screen."""
        for direction in ("left", "right"):
            for _ in range(max_swipes):
                if self._on_screen(exact_text(title)):
                    return
                self._swipe_cards(direction)
        if not self._on_screen(exact_text(title)):
            raise AssertionError(f"Card '{title}' not found on the doctor's profile")

    def _card_fee(self):
        el = self._on_screen(self.FEE_AMOUNT)
        return self.read(el) if el else ""

    def card_shows_fee(self, fee):
        """True if the card on screen shows exactly 'Rs. <fee>' (not 'Rs. 200' when fee is 20)."""
        return self._on_screen(exact_text(f"Rs. {fee}")) is not None

    def _book_on_card(self, title, attempts=6):
        """The cards slide by themselves, so: show the card, find its button, check the card is
        STILL on screen, then tap at once. Try again if it slid away in between.
        (A slide in the split second before the tap can still open the wrong card's summary -
        the PC test checks the summary and goes Back to retry in that case.)"""
        for _ in range(attempts):
            self.show_card(title)
            self.scroll_to_text("Book Appointment")
            button = self._on_screen(self.BOOK_BTN)
            if button and self._on_screen(exact_text(title)):
                button.click()
                return
        raise AssertionError(f"Could not tap Book Appointment on the '{title}' card (cards kept sliding)")
    # ---------- OC ----------
    def has_online_option(self):
        try:
            self.show_card(self.VIDEO_CARD_TITLE)
            return True
        except AssertionError:
            return False

    def online_fee(self):
        self.show_card(self.VIDEO_CARD_TITLE)
        return self._card_fee()

    def start_online_consultation(self):
        self._book_on_card(self.VIDEO_CARD_TITLE)

    # ---------- PC ----------
    def select_clinic(self, hospital):
        self.show_card(hospital)

    def clinic_address(self):
        return HOSPITAL_ADDRESS if self.has_text(HOSPITAL_ADDRESS) else ""

    def clinic_fee(self):
        return self._card_fee()

    def book_visit(self, hospital):
        self._book_on_card(hospital)