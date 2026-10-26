from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage, text_contains


class ConfirmationPage(BasePage):
    """'Physical Appointment Request Received!' screen, shown after a PC (in-clinic) booking."""
    TITLE = text_contains("Request Received")
    VIEW_APPOINTMENT = (AppiumBy.ACCESSIBILITY_ID, "View Appointment")
    BACK_BTN = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Back")')

    def is_open(self, timeout=40):
        return self.is_visible(self.TITLE, timeout=timeout)