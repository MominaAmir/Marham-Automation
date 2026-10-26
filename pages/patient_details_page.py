from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage


class PatientDetailsPage(BasePage):
    NAME_FIELD = (AppiumBy.ACCESSIBILITY_ID, "patient_name")
    CONTINUE_BTN = (AppiumBy.ACCESSIBILITY_ID, "btn_patient_continue")

    def is_open(self, timeout=None):
        return self.is_visible(self.NAME_FIELD, timeout=timeout or self.TIMEOUT)

    def name(self):
        return self.text_of(self.NAME_FIELD)

    def tap_continue(self):
        self.tap(self.CONTINUE_BTN)
