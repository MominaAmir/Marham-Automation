"""Doctor app login with EMAIL + password (the phone number is shared with the patient app, so OTP login
is not used). You type the email and password in PowerShell while the test runs - nothing is saved.
It logs the test doctor OUT first.                                   pytest -m doctor_login -s
Runs only when chosen on purpose. Never retried."""
import allure
import pytest

from doctor_test_data import WRONG_PASSWORD
from pages.doctor_home_page import DoctorHomePage
from pages.doctor_login_page import DoctorLoginPage
from utils.doctor_app import restart_doctor_app
from utils.doctor_safety import ask_secret, ask_text, check_doctor, require_marker_selected
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_login]


def _note(text, name):
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


@pytest.mark.flaky(reruns=0)
@allure.title("DLOG: log out, Login with Email, empty form, wrong password, real password, still logged in")
def test_doctor_login(driver, request):
    require_marker_selected(request.config, "doctor_login")
    email = ask_text(request.config, "Test doctor's login EMAIL")
    password = ask_secret(request.config, "Test doctor's PASSWORD (not shown while you type)")
    if not email or not password:
        pytest.skip("Email or password not typed: run with -s and type them when asked (nothing was changed)")
    home, login = DoctorHomePage(driver), DoctorLoginPage(driver)

    with step("DLOG-01"):
        if not login.is_open(timeout=3):
            assert home.is_loaded(), "Doctor home ('Overview') did not load"
            check_doctor(home.doctor_name())            # only ever log out the test doctor
            home.logout()
        assert login.is_open(timeout=20), "'Enter your mobile number' did not open after Log Out"

    with step("DLOG-02"):
        login.open_email_login()
        assert login.email_screen_open(), "'Welcome back' (Login with Email) did not open"
        assert len(login.boxes()) >= 2, "Email and Password boxes not found"
        assert login.is_visible(login.LOGIN, timeout=5), "Login button not found"

    with step("DLOG-03"):
        login.tap_login()                               # both boxes empty
        assert not home.is_loaded(timeout=5), "Logged in with an EMPTY email and password"
        assert login.email_screen_open(timeout=3), "Left 'Welcome back' with an empty form"

    with step("DLOG-04"):
        login.fill_email(email)
        login.fill_password(WRONG_PASSWORD)
        before = login.texts()
        login.tap_login()
        shown = login.new_texts(before)
        _note(" / ".join(shown) or "no message", "wrong password - what the app showed")
        print(f"\nWRONG PASSWORD -> app showed: {' / '.join(shown) or 'no message'}")
        assert not home.is_loaded(timeout=5), "Logged in with a WRONG password"
        assert login.email_screen_open(timeout=3), "Left 'Welcome back' after a wrong password"

    with step("DLOG-05"):
        login.fill_password(password)
        login.tap_login()
        home.dismiss_popups()
        assert home.is_loaded(), "Home ('Overview') did not open after the correct email and password"
        check_doctor(home.doctor_name())

    with step("DLOG-06"):
        restart_doctor_app(driver)
        assert home.is_loaded(), "Home did not load after restarting the app"
        assert not login.is_open(timeout=3), "Logged out after restarting the app"
        check_doctor(home.doctor_name())