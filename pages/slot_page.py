from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException

from pages.base_page import BasePage, text_contains


def _matches(regex):
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textMatches("{regex}")')


class SlotPage(BasePage):
    """The "Booking Summary" screen: dates, time slots, Appointment For, Payment Summary, Book button."""
    TITLE = text_contains("Booking Summary")
    DATE_CHIP = _matches("[0-9]{1,2} [A-Z][a-z]{2}")              # e.g. "16 Oct"
    TIME_SLOT = _matches("[0-9]{1,2}:[0-9]{2} [AP]M")             # e.g. "09:20 AM"
    AMOUNT = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textStartsWith("Rs.")')
    BOOK_BTN = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Book Appointment")')

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def slots_loaded(self):
        return self.is_visible(self.TIME_SLOT, timeout=self.TIMEOUT)

    def shows(self, text):
        """True if `text` is anywhere on this long screen (scrolls to find it)."""
        try:
            self.scroll_to_text(text)
            return True
        except TimeoutException:
            return False

    def pick_first_free_slot(self):
        """Tap the first date and the first time slot. Returns (date_text, time_text)."""
        self.scroll_to_text("Available Slots")
        date_el = self.find(self.DATE_CHIP)
        date_text = self.read(date_el)
        date_el.click()
        slot_el = self.find(self.TIME_SLOT)
        time_text = self.read(slot_el)
        slot_el.click()
        return date_text, time_text

    def select_patient(self, name):
        """Under "Appointment For", tap the patient with this name (the test patient = Self)."""
        self.scroll_to_text("Appointment For")
        self.scroll_to_text(name).click()

    def _bottom_most(self, locator):
        els = [e for e in self.driver.find_elements(*locator) if e.is_displayed()]
        return max(els, key=lambda e: e.rect["y"]) if els else None

    def total_amount(self):
        self.scroll_to_text("Total Amount")
        el = self._bottom_most(self.AMOUNT)
        return self.read(el) if el else ""

    def book_button(self):
        """The final Book Appointment button at the bottom (not the section title with the same words)."""
        self.scroll_to_text("Total Amount")
        return self._bottom_most(self.BOOK_BTN)

    def book_button_enabled(self):
        button = self.book_button()
        return bool(button) and button.is_enabled()

    def tap_book(self):
        button = self.book_button()
        assert button, "Final 'Book Appointment' button not found"
        button.click()
    def scroll_to_bottom(self, max_swipes=8):
        size = self.driver.get_window_size()
        area = {"left": int(size["width"] * 0.1), "top": int(size["height"] * 0.25),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5)}
        for _ in range(max_swipes):
            if not self.driver.execute_script("mobile: scrollGesture", {**area, "direction": "down", "percent": 0.9}):
                break

    def final_book_button_shown(self):
        """True if the final Book Appointment button is on screen (it sits at the bottom, below the slots)."""
        self.scroll_to_bottom()
        height = self.driver.get_window_size()["height"]
        return any(e.is_displayed() and e.rect["y"] > height * 0.6
                   for e in self.driver.find_elements(*self.BOOK_BTN))

    # ---------- "Appointment Details" pop-up (opens after the final Book Appointment) ----------
    POPUP_TITLE = text_contains("Appointment Details")
    CHANGE_BTN = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Change")')

    def popup_open(self, timeout=None):
        return self.is_visible(self.POPUP_TITLE, timeout=timeout or self.TIMEOUT)

    def _popup_band(self):
        """Top and bottom (y) of the pop-up: from its title down to its Change button."""
        return self.find(self.POPUP_TITLE).rect["y"], self.find(self.CHANGE_BTN).rect["y"]

    def popup_has(self, text):
        top, bottom = self._popup_band()
        return any(top <= e.rect["y"] <= bottom for e in self.driver.find_elements(*text_contains(text)))

    def confirm_popup(self):
        """Tap the pop-up's own Book Appointment (not the one on the screen behind it)."""
        top, bottom = self._popup_band()
        buttons = [e for e in self.driver.find_elements(*self.BOOK_BTN) if top < e.rect["y"] < bottom]
        assert buttons, "Book Appointment button not found inside the pop-up"
        buttons[0].click()