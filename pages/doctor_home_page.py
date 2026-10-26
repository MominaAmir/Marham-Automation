"""Doctor app (Marham Connect) - home screen, bottom tabs and Log Out.
Locators from Appium Inspector, 21 Oct 2026 (app version 13.8.0)."""
import re
import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException

from pages.base_page import BasePage

UI = AppiumBy.ANDROID_UIAUTOMATOR


def exact(text):
    return (UI, f'new UiSelector().text("{text}")')


def tab(name):
    """Bottom tab: android.view.View, content-desc '<icon>, Home' / '<icon>, Appointments' / ..."""
    return (UI, f'new UiSelector().className("android.view.View").descriptionMatches(".*, {name}")')


class DoctorHomePage(BasePage):
    TITLE = exact("Overview")
    TABS = ("Home", "Appointments", "Patients", "Profile")
    LOG_OUT = (AppiumBy.ACCESSIBILITY_ID, "Log Out")           # Profile tab, bottom of the list

    def is_loaded(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def doctor_name(self):
        """The name above 'Overview' (e.g. 'DR. UNAIZA NISAR TESTING'), or ''.
        Read from ONE page-source call (asking for every text one by one was slow)."""
        root = ET.fromstring(self.driver.page_source.encode("utf-8"))
        title_y, names = None, []
        for n in root.iter():
            numbers = re.findall(r"\d+", n.get("bounds") or "")
            if n.get("class") != "android.widget.TextView" or len(numbers) != 4:
                continue
            text, y = (n.get("text") or "").strip(), int(numbers[1])
            if text == "Overview":
                title_y = y
            elif len(text) > 3 and any(c.isalpha() for c in text):
                names.append((y, text))
        above = [item for item in names if title_y is not None and item[0] < title_y]
        return min(above)[1] if above else ""                 # the top-most text = the name

    def open_tab(self, name):
        self.tap(tab(name))

    def _scroll_down(self):
        size = self.driver.get_window_size()
        try:
            return self.driver.execute_script("mobile: scrollGesture", {
                "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.25),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5),
                "direction": "down", "percent": 0.8})
        except WebDriverException:
            return False

    def logout(self):
        """Profile tab -> scroll down -> Log Out (the app logs out at once, no confirmation)."""
        self.open_tab("Profile")
        for _ in range(5):
            if self.is_visible(self.LOG_OUT, timeout=2):
                break
            self._scroll_down()
        self.tap(self.LOG_OUT)