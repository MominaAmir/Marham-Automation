"""Doctor app session, and switching between the doctor app and the patient app on the same phone."""
import pytest

from config.capabilities import android_options
from doctor_test_data import DOCTOR_APP_ACTIVITY, DOCTOR_APP_PACKAGE
from test_data import APP_PACKAGE


def doctor_options():
    o = android_options()
    o.app_package = DOCTOR_APP_PACKAGE
    o.app_activity = DOCTOR_APP_ACTIVITY
    return o


def check_doctor_app_settings():
    if "REPLACE" in DOCTOR_APP_PACKAGE or "REPLACE" in DOCTOR_APP_ACTIVITY:
        pytest.exit("Fill in DOCTOR_APP_PACKAGE and DOCTOR_APP_ACTIVITY in doctor_test_data.py first.",
                    returncode=4)


def restart_doctor_app(driver):
    """Close the doctor app and open it again."""
    driver.terminate_app(DOCTOR_APP_PACKAGE)
    driver.activate_app(DOCTOR_APP_PACKAGE)


def to_patient_app(driver):
    """Bring the patient app to the front, freshly started (its lists only refresh after a reload)."""
    driver.terminate_app(APP_PACKAGE)
    driver.activate_app(APP_PACKAGE)


def to_doctor_app(driver, fresh=True):
    if fresh:
        driver.terminate_app(DOCTOR_APP_PACKAGE)
    driver.activate_app(DOCTOR_APP_PACKAGE)