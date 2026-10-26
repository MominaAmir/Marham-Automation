from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage, text_contains


class SearchPage(BasePage):
    SEARCH_INPUT = (AppiumBy.CLASS_NAME, "android.widget.EditText")
    RESULT_CARD = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.TextView").text("Dermatologist")')
    NO_RESULTS = text_contains("No results found")   # the app's exact no-results wording
    def search(self, text):
        self.enter(self.SEARCH_INPUT, text)
        self.press_search_key()

    def has_result(self, name):
        return self.has_text(name, timeout=self.TIMEOUT)

    def result_count(self):
        return len(self.find_all(self.RESULT_CARD))

    def no_results_shown(self):
        return self.is_visible(self.NO_RESULTS, timeout=self.TIMEOUT)

    def open_result(self, name):
        self.tap(text_contains(name))
