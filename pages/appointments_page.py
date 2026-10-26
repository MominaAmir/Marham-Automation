from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage
from pages.home_page import HomePage


class AppointmentsPage(BasePage):
    UPCOMING_TAB = (AppiumBy.ACCESSIBILITY_ID, "tab_upcoming")
    STATUS = (AppiumBy.ACCESSIBILITY_ID, "appointment_status")         # on the appointment details screen
    CANCEL_BTN = (AppiumBy.ACCESSIBILITY_ID, "btn_cancel_appointment")
    CANCEL_REASON = (AppiumBy.ACCESSIBILITY_ID, "cancel_reason")       # first reason option, if the app asks
    CANCEL_YES = (AppiumBy.ACCESSIBILITY_ID, "btn_cancel_yes")
    CANCEL_NO = (AppiumBy.ACCESSIBILITY_ID, "btn_cancel_no")

    def open(self):
        HomePage(self.driver).open_appointments()
        if self.is_visible(self.UPCOMING_TAB, timeout=5):
            self.tap(self.UPCOMING_TAB)

    def has_active_booking(self, doctor):
        return self.has_text(doctor, timeout=8)

    def open_booking(self, doctor):
        """Open the details of the (only) upcoming booking with this doctor."""
        self.scroll_to_text(doctor).click()

    def status(self):
        return self.text_of(self.STATUS)

    def start_cancel(self):
        self.tap(self.CANCEL_BTN)

    def keep_booking(self):
        self.tap(self.CANCEL_NO)

    def confirm_cancel(self):
        if self.is_visible(self.CANCEL_REASON, timeout=3):
            self.tap(self.CANCEL_REASON)
        self.tap(self.CANCEL_YES)

    def cancel_booking(self, doctor):
        """Used by the clean-up: open the booking and cancel it."""
        self.open_booking(doctor)
        self.start_cancel()
        self.confirm_cancel()

    def cancel_button_visible(self):
        return self.is_visible(self.CANCEL_BTN, timeout=5)
