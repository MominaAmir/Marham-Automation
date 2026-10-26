from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def text_contains(text):
    """Locator for a label/button (TextView) whose text contains `text`. Never matches typed text in a box."""
    return (AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().className("android.widget.TextView").textContains("{text}")')

# Pop-ups that can appear on launch and block taps. Add any new one you see in a failure screenshot.
POPUP_CLOSE_BUTTONS = [
    (AppiumBy.ID, "com.android.permissioncontroller:id/permission_allow_button"),  # Android permission prompt
    (AppiumBy.ACCESSIBILITY_ID, "popup_close"),                                     # REPLACE: in-app promo / rating pop-up
]


class BasePage:
    TIMEOUT = 20

    def __init__(self, driver):
        self.driver = driver

    # ---------- waiting and finding ----------
    def _wait(self, timeout=None):
        return WebDriverWait(self.driver, timeout or self.TIMEOUT)

    def find(self, locator, timeout=None):
        return self._wait(timeout).until(EC.visibility_of_element_located(locator))

    def find_all(self, locator, timeout=None):
        return self._wait(timeout).until(EC.presence_of_all_elements_located(locator))

    def is_visible(self, locator, timeout=3):
        try:
            self.find(locator, timeout)
            return True
        except TimeoutException:
            return False

    def has_text(self, text, timeout=5):
        return self.is_visible(text_contains(text), timeout)

    # ---------- actions ----------
    def tap(self, locator, timeout=None):
        self._wait(timeout).until(EC.element_to_be_clickable(locator)).click()

    def enter(self, locator, text):
        field = self.find(locator)
        field.clear()
        field.send_keys(text)
        self.hide_keyboard()

    def hide_keyboard(self):
        try:
            if self.driver.is_keyboard_shown():
                self.driver.hide_keyboard()
        except WebDriverException:
            pass

    def press_search_key(self):
        self.driver.execute_script("mobile: performEditorAction", {"action": "search"})

    def back(self):
        self.driver.back()

    def scroll_to_text(self, text, max_swipes=6):
        """Scroll the screen (like a finger) until an element containing `text` is visible, then return it."""
        locator = text_contains(text)
        if self.is_visible(locator, timeout=2):
            return self.find(locator)
        size = self.driver.get_window_size()
        area = {"left": int(size["width"] * 0.1), "top": int(size["height"] * 0.25),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5)}
        for direction in ("down", "up"):
            for _ in range(max_swipes):
                can_scroll_more = self.driver.execute_script(
                    "mobile: scrollGesture", {**area, "direction": direction, "percent": 0.7})
                if self.is_visible(locator, timeout=1):
                    return self.find(locator)
                if not can_scroll_more:
                    break
        raise TimeoutException(f"'{text}' not found on the screen, even after scrolling")

    def dismiss_popups(self):
        for locator in POPUP_CLOSE_BUTTONS:
            if self.is_visible(locator, timeout=1):
                self.tap(locator)

    # ---------- reading ----------
    @staticmethod
    def read(element):
        """Visible text, or the content-desc when the element has no text."""
        return element.text or element.get_attribute("content-desc") or ""

    def text_of(self, locator):
        return self.read(self.find(locator))

    def is_enabled(self, locator):
        return self.find(locator).is_enabled()
