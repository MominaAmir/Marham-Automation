from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage, text_contains


class HomePage(BasePage):
    # REPLACE every locator with the value from your Step 4 locator sheet
    SEARCH_BAR = text_contains("Search for Doctors")                   # only on the home screen
    LOGIN_PROMPT = (AppiumBy.ACCESSIBILITY_ID, "btn_login")            # only shown when logged OUT
    APPOINTMENTS_TAB = text_contains("Bookings")
    PROFILE_TAB = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Profile")')   # bottom tab
    ERROR_MESSAGE = text_contains("Something went wrong")              # the app's generic error text

    def is_loaded(self):
        return self.is_visible(self.SEARCH_BAR, timeout=self.TIMEOUT)

    def has_error(self):
        return self.is_visible(self.ERROR_MESSAGE, timeout=2)

    def is_logged_out(self):
        return self.is_visible(self.LOGIN_PROMPT, timeout=3)

    def open_search(self):
        self.tap(self.SEARCH_BAR)

    def open_appointments(self):
        self.tap(self.APPOINTMENTS_TAB)

    def open_profile(self):
        self.tap(self.PROFILE_TAB)
        return self.has_text("Friends & Family", timeout=self.TIMEOUT)
