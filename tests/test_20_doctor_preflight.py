"""Doctor app preflight: phone, app, version, test doctor logged in.     pytest -m doctor_preflight
If it fails, the other doctor app tests in the same run are skipped."""
import allure
import pytest

from doctor_test_data import DOCTOR_APP_PACKAGE, DOCTOR_EXPECTED_APP_VERSION
from pages.doctor_home_page import DoctorHomePage
from pages.doctor_login_page import DoctorLoginPage
from utils import adb
from utils.doctor_safety import check_doctor
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_preflight]


@allure.title("DPRE: phone, doctor app version and test doctor login are ready")
def test_doctor_preflight(driver):
    with step("DPRE-01"):
        assert not driver.is_locked(), "Phone screen is locked: unlock it and turn screen lock off"

    with step("DPRE-02"):
        assert driver.is_app_installed(DOCTOR_APP_PACKAGE), f"{DOCTOR_APP_PACKAGE} is not installed"

    with step("DPRE-03"):
        version = adb.app_version(DOCTOR_APP_PACKAGE)
        allure.attach(version, name="doctor app version", attachment_type=allure.attachment_type.TEXT)
        print(f"\nDoctor app version on the phone: {version}")
        if DOCTOR_EXPECTED_APP_VERSION:
            assert version == DOCTOR_EXPECTED_APP_VERSION, (
                f"Phone has {version}, expected {DOCTOR_EXPECTED_APP_VERSION}: update the app or doctor_test_data.py")

    home, login = DoctorHomePage(driver), DoctorLoginPage(driver)
    with step("DPRE-04"):
        assert home.is_loaded() or login.is_open(timeout=5), \
            "Neither the doctor home ('Overview') nor the login screen opened"

    with step("DPRE-05"):
        assert not login.is_open(timeout=2), "Doctor app is logged out: run  pytest -m doctor_login -s"
        check_doctor(home.doctor_name())                # another doctor = the whole run stops