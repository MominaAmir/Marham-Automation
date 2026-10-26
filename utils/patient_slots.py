"""Patient app, READ-ONLY: open the test doctor's Booking Summary for one location and read the time slots
offered per day. Nothing is booked (Book Appointment is never tapped on the summary).

Booking Summary (Inspector 23 Oct 2026): doctor card ('Dr. Momina Testing', location, 'Fee: Rs. 2'),
'Book Appointment', date chips = ViewGroup content-desc 'Fri, 23 Oct' / 'Sat, 24 Oct' ...,
'Available Slots' grouped Morning / Afternoon / ..., each slot a text like '10:00 AM'."""
import datetime
import re
import time
import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException

from doctor_test_data import PATIENT_APP_DOCTOR_NAME
from pages.base_page import BasePage
from pages.doctor_appointments_page import clean
from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from utils.doctor_app import to_patient_app
from utils.doctor_safety import doctor_stop
from utils.patient_side import _steady

TIME_RE = re.compile(r"^\d{1,2}:\d{2} [AP]M$")
CHIP_RE = re.compile(r"^[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2}$")          # Sat, 24 Oct


def chip_desc(day):
    return f"{day:%a}, {day.day} {day:%b}"


def _scroll(driver, direction, percent=0.6):
    size = driver.get_window_size()
    try:
        return driver.execute_script("mobile: scrollGesture", {
            "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.35),
            "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.45),
            "direction": direction, "percent": percent})
    except WebDriverException:
        return False


def open_summary(driver, place):
    """Patient app -> search -> test doctor's profile -> place's card -> Booking Summary. Returns the
    fee shown on the card. Stops the run if the profile is not the test doctor."""
    to_patient_app(driver)
    home = HomePage(driver)
    assert home.is_loaded(), "Patient app home did not load"
    BasePage(driver).dismiss_popups()
    LoginPage(driver).ensure_logged_in()
    home.open_search()
    search = SearchPage(driver)
    search.search(PATIENT_APP_DOCTOR_NAME)
    assert search.has_result(PATIENT_APP_DOCTOR_NAME), f"{PATIENT_APP_DOCTOR_NAME} not in the search results"
    search.open_result(PATIENT_APP_DOCTOR_NAME)
    profile = DoctorProfilePage(driver)
    if not profile.has_text(PATIENT_APP_DOCTOR_NAME, timeout=profile.TIMEOUT):
        doctor_stop(f"opened profile does not show the test doctor '{PATIENT_APP_DOCTOR_NAME}'")
    _steady(profile.show_card, place)
    _steady(profile.show_card, place)
    fee = _steady(profile.clinic_fee)
    summary = SlotPage(driver)
    for _ in range(3):                                 # cards slide by themselves: retry if the wrong one opened
        _steady(profile._book_on_card, place)
        assert summary.is_open(), "Booking Summary did not open"
        if summary.has_text(place, timeout=5) or summary.shows(place):
            break
        summary.back()
    else:
        doctor_stop(f"Booking Summary does not show '{place}' after 3 tries")
    summary.scroll_to_text("Book Appointment")
    return fee


def date_chips(driver):
    """The date chips' descriptions in screen order (left to right)."""
    root = ET.fromstring(driver.page_source.encode("utf-8"))
    chips = []
    for n in root.iter():
        desc = clean(n.get("content-desc"))
        if CHIP_RE.match(desc) and desc not in chips:
            chips.append(desc)
    return chips


def _times_on_screen(driver):
    root = ET.fromstring(driver.page_source.encode("utf-8"))
    return [clean(n.get("text")) for n in root.iter() if TIME_RE.match(clean(n.get("text")))]


def slots_for(driver, day, max_swipes=10):
    """Tap the day's chip and read every slot of that day (scrolls down, then back to the chips)."""
    desc = chip_desc(day)
    chips = driver.find_elements(AppiumBy.ACCESSIBILITY_ID, desc)
    if not chips:
        return None                                    # no chip for this day (no slots that day?)
    chips[0].click()
    time.sleep(2)
    found = []
    last = False                                   # the final scroll still moves the screen: read once more
    for _ in range(max_swipes + 1):
        found += [t for t in _times_on_screen(driver) if t not in found]
        if last:
            break
        last = not _scroll(driver, "down")
    for _ in range(max_swipes):                       # back up, so the next day's chip is on screen
        if not _scroll(driver, "up", 1.0):
            break
    # the page source does not always list the slots in time order: sort them
    return sorted({datetime.datetime.combine(day, datetime.datetime.strptime(t, "%I:%M %p").time()) for t in found})


def offered_slots(driver, place, days, max_swipes=10):
    """{date: [datetime, ...] or None} for each date in days, from the Booking Summary of place.
    Waits for screens to settle while in the patient app (the profile cards slide)."""
    driver.update_settings({"waitForIdleTimeout": 10000})
    try:
        fee = open_summary(driver, place)
        chips = date_chips(driver)
        return fee, chips, {day: slots_for(driver, day, max_swipes) for day in days}
    finally:
        driver.update_settings({"waitForIdleTimeout": 0})