"""Friends & Family (Profile tab), its 'Add New Member' sheet and 'Delete Member' pop-up,
and the same 'Add New Member' sheet opened from Booking Summary -> Appointment For.

Safety: only members whose name starts with FAMILY_TEST_PREFIX ("Autotest ") can ever be deleted."""
import random
import re
import string
import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support import expected_conditions as EC

from pages.base_page import BasePage, text_contains
from pages.doctor_profile_page import DoctorProfilePage
from pages.home_page import HomePage
from pages.search_page import SearchPage
from pages.slot_page import SlotPage
from test_data import DOCTOR_NAME, FAMILY_TEST_PREFIX
from utils.safety import check_profile_is_test_doctor, stop_run


def exact(text):
    """Element whose text is exactly `text`."""
    return (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{text}")')


def _center_y(element):
    r = element.rect
    return r["y"] + r["height"] / 2


def _digits(text):
    return re.sub(r"[^0-9]", "", text or "")


def new_test_name():
    """'Autotest Kqzm': the prefix + 4 random letters (letters only, new every run)."""
    letters = "".join(random.choice(string.ascii_lowercase) for _ in range(4))
    return f"{FAMILY_TEST_PREFIX} {letters.capitalize()}"


def new_short_phone(prefix):
    """A different 7-digit number every run, e.g. '0300' + '417' (a number already saved on another
    member may be refused, which would hide what the step is really checking)."""
    return prefix[:4] + "".join(random.choice(string.digits) for _ in range(3))


def is_test_member(name):
    return name.startswith(FAMILY_TEST_PREFIX + " ")


def open_test_doctor_summary(driver):
    """Home -> search the test doctor -> profile (exact name check) -> Video Consultation card ->
    Booking Summary -> first date + first time slot (Appointment For, with its Add New Member,
    only appears after a slot is chosen). Book Appointment is never tapped, so nothing is booked."""
    HomePage(driver).open_search()
    search = SearchPage(driver)
    search.search(DOCTOR_NAME)
    search.open_result(DOCTOR_NAME)
    profile = DoctorProfilePage(driver)
    check_profile_is_test_doctor(profile.name())   # wrong doctor = whole run stops
    profile.start_online_consultation()
    summary = SlotPage(driver)
    assert summary.is_open(), "Booking Summary did not open"
    assert summary.slots_loaded(), "No time slots shown on Booking Summary"
    summary.pick_first_free_slot()                # choosing a slot books nothing
    return summary


class MemberSheet(BasePage):
    """The 'Add New Member' sheet. From Profile: name, phone, 8 relationships (no gender).
    From Booking Summary: name, phone, 6 relationships + Gender Male / Female."""
    TITLE = exact("Add New Member")
    # Booking Summary's own "+ Add New Member" button has the same words as the title,
    # so the sheet is recognised by its "Full Name" label instead.
    ANCHOR = exact("Full Name")
    LABELS = ("Full Name", "Phone Number (optional)", "Relationship")
    NAME_HINT = "Enter name"
    PHONE_HINT = "03XX-XXXXXXX"
    ADD_BTN = exact("Add Member")
    ALERT_MESSAGE = (AppiumBy.ID, "android:id/message")
    ALERT_OK = (AppiumBy.ID, "android:id/button1")
    ERROR_WORDS = re.compile(r"(?i)\b(digits?|invalid|valid|incorrect|at least|must|required)\b")

    def is_open(self, timeout=None):
        return self.is_visible(self.ANCHOR, timeout=timeout or self.TIMEOUT)

    def wait_closed(self, timeout=15):
        try:
            self._wait(timeout).until(EC.invisibility_of_element_located(self.ANCHOR))
            return True
        except TimeoutException:
            return False

    def _below_title(self, locator):
        """Elements under the sheet's 'Full Name' label (cards behind the sheet can have the same words)."""
        top = self.find(self.ANCHOR).rect["y"]
        return sorted((e for e in self.driver.find_elements(*locator) if e.rect["y"] > top),
                      key=lambda e: e.rect["y"])

    # ---------- typing ----------
    def _edit_text(self, current):
        """The text box that now shows `current` (its hint when empty, or the typed value)."""
        for box in self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText"):
            shown = box.text or ""
            if shown == current or (_digits(current) and _digits(shown) == _digits(current)):
                return box
        raise AssertionError(f"No text box showing '{current}' in Add New Member")

    # The keyboard is NOT closed after typing: closing it makes the sheet slide down, and a tap made
    # while it is still moving lands where the button WAS (that is why Add Member was not tapped).
    # The Add Member button stays visible above the keyboard, so the tests choose the relationship
    # first and type last.
    def fill(self, hint, value):
        """Type into the empty box with this hint ('Enter name' or '03XX-XXXXXXX')."""
        box = self._edit_text(hint)
        box.click()
        box.send_keys(value)

    def refill(self, old_value, new_value):
        box = self._edit_text(old_value)
        box.click()
        box.clear()
        box.send_keys(new_value)

    def _tap_when_still(self, element):
        """Wait until the element stops moving, then tap the middle of it with a real finger tap."""
        rect = element.rect
        for _ in range(10):
            time.sleep(0.3)
            now = element.rect
            if now == rect:
                break
            rect = now
        self.driver.execute_script("mobile: clickGesture", {"x": int(rect["x"] + rect["width"] / 2),
                                                            "y": int(rect["y"] + rect["height"] / 2)})

    # ---------- choices ----------
    def chip(self, label):
        """The Relationship chip with this exact label, or None."""
        found = self._below_title(exact(label))
        return found[0] if found else None

    def choose(self, relation):
        chip = self.chip(relation)
        assert chip, f"Relationship '{relation}' not in Add New Member"
        self._tap_when_still(chip)

    def has_gender(self, gender):
        return self.is_visible((AppiumBy.ACCESSIBILITY_ID, gender), timeout=3)

    def choose_gender(self, gender):
        self._tap_when_still(self.find((AppiumBy.ACCESSIBILITY_ID, gender)))

    # ---------- saving ----------
    def _add_button(self):
        if not self.is_visible(self.ADD_BTN, timeout=5):
            self.hide_keyboard()                             # only if the keyboard really covers it
        return self.find(self.ADD_BTN)

    def _reacted(self, wait=3):
        """True if the app answered the tap within `wait` seconds: banner, alert, error text,
        the sheet closed, or the button turned into a loading spinner."""
        end = time.time() + wait
        while time.time() < end:
            banners = self.driver.find_elements(*text_contains("added to your family"))
            if banners:
                self.last_banner = banners[0].text or ""     # remembered: the banner only stays ~3 s
            if (banners
                    or self.driver.find_elements(*self.ALERT_MESSAGE)
                    or not self.driver.find_elements(*self.ANCHOR)
                    or not self.driver.find_elements(*self.ADD_BTN)
                    or any(self.ERROR_WORDS.search(e.text or "") for e in
                           self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"))):
                return True
            time.sleep(0.5)
        return False

    def tap_add(self):
        """Tap Add Member. If the app shows no reaction at all within 3 s, the tap was lost: tap once more.
        (With an empty form nothing happens either way - the button is greyed out.)"""
        self.last_banner = ""
        self._tap_when_still(self._add_button())
        if not self._reacted():
            self._tap_when_still(self._add_button())

    def added_message(self, name, timeout=15):
        """Green banner '<name> added to your family' - seen right after the tap, or on screen now."""
        if f"{name} added to your family" in getattr(self, "last_banner", ""):
            return True
        return self.is_visible(text_contains(f"{name} added to your family"), timeout=timeout)

    def alert_text(self, timeout=3):
        return self.text_of(self.ALERT_MESSAGE) if self.is_visible(self.ALERT_MESSAGE, timeout) else ""

    def close_alert(self):
        if self.is_visible(self.ALERT_OK, timeout=2):
            self.tap(self.ALERT_OK)

    def error_texts(self):
        """Form errors on screen: an Android alert, or a message like 'enter a valid 11 digit number'."""
        found = []
        alert = self.alert_text(timeout=2)
        if alert:
            found.append(alert)
        for el in self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
            t = (el.text or "").strip()
            if t and t not in found and t not in self.LABELS and self.ERROR_WORDS.search(t):
                found.append(t)
        return found

    def nothing_added(self, wait=4):
        """After tapping Add Member: no 'added' banner and the sheet is still open.
        Any alert is read and closed; returns (nothing_added, alert_text)."""
        alert = self.alert_text(timeout=wait)
        self.close_alert()
        added = self.is_visible(text_contains("added to your family"), timeout=1)
        return (not added and self.is_open(timeout=3)), alert


class FriendsFamilyPage(BasePage):
    """Profile -> Friends & Family: one card per member (name, relation tag, 'Gender · +92...', bin icon)."""
    TITLE = exact("Friends & Family")
    ADD_FAMILY_BTN = exact("Add family member")
    INFO = "Add your family members once"
    BINS = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionStartsWith("Remove ")')
    COUNT = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("[0-9]{1,3}")')
    REMOVED_MSG = text_contains("Family member removed")
    DELETE_TITLE = exact("Delete Member")
    DELETE_QUESTION = "Are you sure you want to delete this family member"
    DELETE_BTN = (AppiumBy.ID, "android:id/button1")
    CANCEL_BTN = (AppiumBy.ID, "android:id/button2")

    def open(self):
        HomePage(self.driver).open_profile()
        self.scroll_to_text("Friends & Family").click()
        return self.is_visible(self.ADD_FAMILY_BTN, timeout=self.TIMEOUT)

    # ---------- reading the list ----------
    @staticmethod
    def _bin(name):
        return (AppiumBy.ACCESSIBILITY_ID, f"Remove {name}")

    def _names_now(self):
        return [(b.get_attribute("content-desc") or "")[len("Remove "):].strip()
                for b in self.driver.find_elements(*self.BINS)]

    def member_names(self, timeout=15):
        """Names in the list, read once the list has stopped changing and matches the count next to
        the title (right after opening, the app can show an older list for a moment)."""
        self.is_visible(self.BINS, timeout=10)             # wait for the list to load
        names, end = self._names_now(), time.time() + timeout
        while time.time() < end:
            time.sleep(2)
            now = self._names_now()
            badge = self.count_badge()
            if now == names and (badge is None or badge == len(now)):
                return now
            names = now
        return names

    def settle(self):
        """Close the keyboard if it stayed open after the form closed (it can cover the last card)."""
        try:
            if self.driver.is_keyboard_shown():
                self.driver.hide_keyboard()
                time.sleep(1)
        except WebDriverException:
            pass

    def _member_elements(self, name):
        """The member's bin icon ('Remove <name>') or, failing that, its name text - present on the
        screen even if Android says it is not 'displayed' (e.g. partly under the keyboard)."""
        return self.driver.find_elements(*self._bin(name)) or self.driver.find_elements(*exact(name))

    def has_member(self, name, timeout=5):
        self.settle()
        end = time.time() + timeout
        while True:
            if self._member_elements(name):
                return True
            if time.time() > end:
                break
            time.sleep(1)
        size = self.driver.get_window_size()                 # maybe below the screen: scroll the list once
        self.driver.execute_script("mobile: scrollGesture", {
            "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3), "width": int(size["width"] * 0.8),
            "height": int(size["height"] * 0.4), "direction": "down", "percent": 0.8})
        return bool(self._member_elements(name))

    def wait_gone(self, name, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            if not self.driver.find_elements(*self._bin(name)):
                return True
            time.sleep(1)
        return False

    def count_badge(self):
        """The number next to the title (e.g. 2), or None if it is not shown."""
        title_y = _center_y(self.find(self.TITLE))
        for el in self.driver.find_elements(*self.COUNT):
            if abs(_center_y(el) - title_y) < 40:
                return int(el.text)
        return None

    def card_text(self, name):
        """All words on this member's card, joined with ' | ' (name, relation, 'Male · +92...')."""
        bins = self.driver.find_elements(*self._bin(name))
        if bins:
            b = bins[0].rect
            middle, right = b["y"] + b["height"] / 2, b["x"]
        else:                                                # no bin found: use the name line instead
            n = self.driver.find_elements(*exact(name))[0].rect
            middle, right = n["y"] + n["height"] / 2 + 15, self.driver.get_window_size()["width"] * 0.8
        texts = [el.text.strip() for el in self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                 if el.text and el.rect["x"] < right and abs(_center_y(el) - middle) < 75]
        return " | ".join(texts)

    # ---------- adding ----------
    def open_add_sheet(self):
        self.tap(self.ADD_FAMILY_BTN)
        return MemberSheet(self.driver).is_open()

    # ---------- deleting (test members only) ----------
    def tap_bin(self, name):
        if not is_test_member(name):
            stop_run(f"tried to delete '{name}', which is not a test member ({FAMILY_TEST_PREFIX} ...)")
        self.settle()
        bins = self.driver.find_elements(*self._bin(name))
        assert bins, f"Bin icon 'Remove {name}' not found"
        bins[0].click()
        return self.is_visible(self.DELETE_TITLE, timeout=10)

    def cancel_delete(self):
        self.tap(self.CANCEL_BTN)

    def confirm_delete(self):
        self.tap(self.DELETE_BTN)

    def delete_member(self, name):
        assert self.tap_bin(name), "'Delete Member' pop-up did not open"
        self.confirm_delete()
        self.is_visible(self.REMOVED_MSG, timeout=10)
        return self.wait_gone(name)

    def leftover_test_members(self):
        return [n for n in self.member_names() if is_test_member(n)]

    def delete_leftovers(self):
        """Delete every 'Autotest ...' member left by an earlier run. Returns their names."""
        removed = []
        for _ in range(10):
            left = self.leftover_test_members()
            if not left:
                break
            assert self.delete_member(left[0]), f"Could not delete old test member '{left[0]}'"
            removed.append(left[0])
        return removed


class AppointmentFor(BasePage):
    """'Appointment For' on Booking Summary: Self + family members (name, relation under it) + Add New Member."""
    ADD_NEW = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("Add New Member")')

    def _name(self, name, max_swipes=6):
        """The member's name, matched EXACTLY (the green banner '<name> added to your family'
        also contains the name). Scrolls down, then up, until it is on screen; None if not found."""
        locator = exact(name)
        if self.is_visible(locator, timeout=2):
            return self.find(locator)
        size = self.driver.get_window_size()
        area = {"left": int(size["width"] * 0.1), "top": int(size["height"] * 0.25),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5)}
        for direction in ("down", "up"):
            for _ in range(max_swipes):
                more = self.driver.execute_script("mobile: scrollGesture",
                                                  {**area, "direction": direction, "percent": 0.7})
                if self.is_visible(locator, timeout=1):
                    return self.find(locator)
                if not more:
                    break
        return None

    def has_member(self, name):
        return self._name(name) is not None

    def relation_of(self, name):
        """The small word under the member's name (Self, Sister, Son ...)."""
        el = self._name(name)
        if el is None:
            return ""
        n = el.rect
        for other in self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
            r = other.rect
            if other.text and n["y"] + n["height"] - 5 <= r["y"] <= n["y"] + n["height"] + 60 \
                    and abs(r["x"] - n["x"]) < 40:
                return other.text.strip()
        return ""

    def open_add_sheet(self):
        self.scroll_to_text("Add New Member")
        if self.is_visible(self.ADD_NEW, timeout=3):
            self.tap(self.ADD_NEW)
        else:
            self.find(text_contains("Add New Member")).click()
        return MemberSheet(self.driver).is_open()