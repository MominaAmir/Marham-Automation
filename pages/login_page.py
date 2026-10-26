import os

import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage
from pages.home_page import HomePage
from test_data import TEST_PHONE


class LoginPage(BasePage):
    PHONE_INPUT = (AppiumBy.ACCESSIBILITY_ID, "login_phone")
    CONTINUE_BTN = (AppiumBy.ACCESSIBILITY_ID, "login_continue")
    OTP_INPUT = (AppiumBy.ACCESSIBILITY_ID, "login_otp")
    VERIFY_BTN = (AppiumBy.ACCESSIBILITY_ID, "login_verify")

    def ensure_logged_in(self):
        home = HomePage(self.driver)
        if not home.is_logged_out():
            return
        otp = os.environ.get("MARHAM_TEST_OTP")
        if not otp:
            pytest.fail("Test patient is logged out. Log in by hand once on the phone "
                        "(noReset keeps the session), or set MARHAM_TEST_OTP for the fixed OTP.")
        home.tap(home.LOGIN_PROMPT)
        self.enter(self.PHONE_INPUT, TEST_PHONE)
        self.tap(self.CONTINUE_BTN)
        self.enter(self.OTP_INPUT, otp)
        self.tap(self.VERIFY_BTN)
        assert home.is_loaded(), "Home screen did not load after login"
        assert not home.is_logged_out(), "Still logged out after entering the OTP"
