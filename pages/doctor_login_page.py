"""Doctor app (Marham Connect) - 'Enter your mobile number' and 'Verify Phone Number' (OTP) screens.
Locators from Appium Inspector, 21 Oct 2026 (app version 13.8.0)."""
import re
import time

from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage, text_contains
from pages.doctor_home_page import exact

BOX = (AppiumBy.CLASS_NAME, "android.widget.EditText")


def button(label):
    """Buttons in this app are ViewGroups whose content-desc is their label (Verify, Login, Log Out)."""
    return (AppiumBy.ACCESSIBILITY_ID, label)


def local_number(phone):
    """'03116771305', '+923116771305' or '3116771305' -> '3116771305' (the box already shows +92)."""
    digits = re.sub(r"[^0-9]", "", phone)
    if digits.startswith("92"):
        digits = digits[2:]
    return digits.lstrip("0")


class DoctorLoginPage(BasePage):
    TITLE = exact("Enter your mobile number")
    CONTINUE = "Continue"
    OTP_TITLE = exact("Verify Phone Number")
    OTP_EXPIRY = "OTP will expire after 1 minute"
    VERIFY = button("Verify")
    OTP_ERROR = text_contains("Invalid or expired OTP")
    SKIP = exact("Skip")                                     # intro screen "Grow Your Practice"

    # ---------- mobile number ----------
    def skip_intro(self):
        """The intro ('Grow Your Practice', Continue / Skip) shows once after a fresh start while
        logged out. Tap Skip if it is there. Returns True if it was skipped."""
        if self.is_visible(self.SKIP, timeout=3):
            self.tap(self.SKIP)
            return True
        return False

    def is_open(self, timeout=5):
        self.skip_intro()
        return self.is_visible(self.TITLE, timeout=timeout)

    def enter_phone(self, phone):
        box = self.find(BOX)
        box.click()
        box.clear()
        box.send_keys(local_number(phone))

    def tap_continue(self):
        """Tap Continue (by content-desc, or by its text if it has none)."""
        for locator in (button(self.CONTINUE), exact(self.CONTINUE)):
            found = self.driver.find_elements(*locator)
            if found:
                found[0].click()
                return
        raise AssertionError("Continue button not found on 'Enter your mobile number'")

    # ---------- OTP ----------
    def otp_screen_open(self, timeout=20):
        return self.is_visible(self.OTP_TITLE, timeout=timeout)

    def enter_otp(self, otp):
        box = self.find(BOX)                                 # one box for the whole code
        box.click()
        box.clear()
        box.send_keys(otp)

    def tap_verify(self):
        self.tap(self.VERIFY)

    def otp_error_shown(self, timeout=8):
        """Red banner 'Invalid or expired OTP' at the top (stays only a few seconds)."""
        end = time.time() + timeout
        while time.time() < end:
            if self.driver.find_elements(*self.OTP_ERROR):
                return True
            time.sleep(0.3)
        return False

    # ---------- Login with Email ('Welcome back') ----------
    EMAIL_LINK = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionMatches(".*Login with Email")')
    EMAIL_TITLE = exact("Welcome back")
    LOGIN = button("Login")                                  # greyed until email + password are typed

    def open_email_login(self):
        self.tap(self.EMAIL_LINK)

    def email_screen_open(self, timeout=15):
        return self.is_visible(self.EMAIL_TITLE, timeout=timeout)

    def boxes(self):
        """The text boxes from top to bottom: [Email, Password]."""
        return sorted(self.driver.find_elements(*BOX), key=lambda b: b.rect["y"])

    def _type(self, index, value):
        box = self.boxes()[index]
        box.click()
        box.clear()
        box.send_keys(value)

    def fill_email(self, email):
        self._type(0, email)

    def fill_password(self, password):
        self._type(1, password)

    def tap_login(self):
        if not self.is_visible(self.LOGIN, timeout=3):
            self.hide_keyboard()                             # only if the keyboard covers the button
        self.find(self.LOGIN).click()

    def texts(self):
        return [(e.text or "").strip() for e in self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                if (e.text or "").strip()]

    def new_texts(self, before, timeout=6):
        """Texts (or a toast) that appeared after a tap, e.g. an error message. [] if nothing new."""
        end = time.time() + timeout
        while time.time() < end:
            found = [t for t in self.texts() if t not in before]
            found += [(e.text or "").strip() for e in self.driver.find_elements(AppiumBy.XPATH, "//android.widget.Toast")
                      if (e.text or "").strip()]
            if found:
                return found
            time.sleep(0.3)
        return []