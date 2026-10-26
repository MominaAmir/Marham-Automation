import allure
import pytest

from pages.home_page import HomePage
from pages.login_page import LoginPage
from test_data import APP_PACKAGE, EXPECTED_APP_VERSION
from utils import adb
from utils.steps import step


@pytest.mark.preflight
@allure.title("PRE: phone, app version and login are ready")
def test_preflight(driver):
    with step("PRE-01"):
        assert not driver.is_locked(), "Phone screen is locked: unlock it and turn screen lock off"

    with step("PRE-02"):
        assert driver.is_app_installed(APP_PACKAGE), f"{APP_PACKAGE} is not installed"

    with step("PRE-03"):
        version = adb.app_version(APP_PACKAGE)
        allure.attach(version, name="app version", attachment_type=allure.attachment_type.TEXT)
        if EXPECTED_APP_VERSION:
            assert version == EXPECTED_APP_VERSION, (
                f"Phone has {version}, expected {EXPECTED_APP_VERSION}: update the app or test_data.py")

    home = HomePage(driver)
    with step("PRE-04"):
        assert home.is_loaded(), "Home screen did not load"
        assert not home.has_error(), "Home screen shows an error message"

    with step("PRE-05"):
        LoginPage(driver).ensure_logged_in()
