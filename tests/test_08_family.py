"""Friends & Family: add a member from Profile and from Booking Summary, check its data and the form
errors, then delete it. Test members are always called 'Autotest <4 letters>' and only they are ever
deleted (Unaiza Nasir, Tooba and Self are never touched). Nothing is booked.   pytest -m family -s"""
import datetime
from pathlib import Path

import allure
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.family_page import (AppointmentFor, FriendsFamilyPage, MemberSheet, new_test_name,
                               open_test_doctor_summary)
from test_data import (FAMILY_BOOKING_GENDER, FAMILY_BOOKING_RELATION, FAMILY_DEFAULT_PHONE_SHOWN,
                       FAMILY_FILL_ALERT, FAMILY_GENDER, FAMILY_MEMBERS, FAMILY_PHONE, FAMILY_RELATION,
                       FAMILY_RELATIONS_BOOKING, FAMILY_RELATIONS_PROFILE, FAMILY_SHORT_PHONE)
from pages.family_page import new_short_phone
from utils.app import restart_app
from utils.steps import step

CLEANUP_FILE = Path(__file__).resolve().parent.parent / "reports" / "MANUAL_CLEANUP_NEEDED.txt"


def _note(text, name):
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def _screenshot(driver, name):
    allure.attach(driver.get_screenshot_as_png(), name=name, attachment_type=allure.attachment_type.PNG)


def _listed_after_add(driver, family, name):
    """True if the new member is in Friends & Family. If it is not there straight away, the app is
    restarted and the list opened again (and that is noted: the list did not refresh by itself)."""
    if family.has_member(name, timeout=15):
        return True
    _screenshot(driver, f"list right after adding {name} (member not found)")
    allure.attach(driver.page_source, name="screen XML right after adding",
                  attachment_type=allure.attachment_type.XML)
    restart_app(driver)
    assert family.open(), "Friends & Family did not open"
    found = family.has_member(name, timeout=15)
    if found:
        _note(f"'{name}' only appeared after reopening Friends & Family (list did not refresh by itself)",
              "possible bug")
        print(f"\nNOTE: '{name}' only appeared after reopening Friends & Family")
    else:                                                   # show what IS there, to see why it was missed
        bins = [b.get_attribute("content-desc") for b in driver.find_elements(*family.BINS)]
        texts = [e.text for e in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView") if e.text]
        print(f"\nLOOKING FOR: {name!r}\nBIN ICONS ON SCREEN: {bins}\nTEXTS ON SCREEN: {texts}")
        _note(f"looking for {name!r}\nbin icons: {bins}\ntexts: {texts}", "what the list shows")
    return found


def _shown_phone(phone):
    """'03116771305' is shown on the card as '+923116771305'."""
    return "+92" + phone[1:]


@pytest.fixture
def family(driver):
    """Friends & Family page. After the test (passed or failed) every 'Autotest ...' member is deleted."""
    page = FriendsFamilyPage(driver)
    yield page
    try:
        restart_app(driver)
        assert page.open(), "Friends & Family did not open"
        removed = page.delete_leftovers()
        if removed:
            _note(", ".join(removed), "clean-up deleted")
    except Exception as exc:
        CLEANUP_FILE.parent.mkdir(exist_ok=True)
        with CLEANUP_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}  Delete the family members named "
                    f"'Autotest ...' by hand (Profile > Friends & Family). Auto clean-up failed: {exc!r}\n")


@pytest.mark.family
@allure.title("FAM: add a family member from Profile, check its data and the form errors, then delete it")
def test_family_add_check_delete(driver, family):
    name = new_test_name()
    _note(name, "test member")
    sheet = MemberSheet(driver)
    section = AppointmentFor(driver)

    with step("FAM-01"):
        assert family.open(), "Friends & Family did not open"
        removed = family.delete_leftovers()                 # left by an earlier failed run
        if removed:
            _note(", ".join(removed), "old test members deleted first")
        assert family.has_text(family.INFO), "Info text 'Add your family members once...' missing"
        names = family.member_names()
        for member in FAMILY_MEMBERS:
            assert member in names, f"'{member}' missing in Friends & Family (shown: {names})"
        before = len(names)
        badge = family.count_badge()
        assert badge == before, f"Count next to the title is {badge}, but {before} members are listed"

    with step("FAM-02"):
        assert family.open_add_sheet(), "'Add New Member' did not open"
        for label in sheet.LABELS:
            assert sheet.has_text(label), f"'{label}' missing in Add New Member"
        for hint in (sheet.NAME_HINT, sheet.PHONE_HINT):
            sheet._edit_text(hint)                          # fails if the empty box is missing
        for relation in FAMILY_RELATIONS_PROFILE:
            assert sheet.chip(relation), f"Relationship '{relation}' missing"

    with step("FAM-03"):
        sheet.tap_add()                                     # empty form
        ok, alert = sheet.nothing_added()
        assert ok, "A member was added with an empty form"
        sheet.choose(FAMILY_RELATION)                       # relationship only, still no name
        sheet.tap_add()
        ok, alert2 = sheet.nothing_added()
        assert ok, "A member was added without a name"
        _note(f"empty form: {alert or 'no message (button does nothing)'}\n"
              f"relationship only: {alert2 or 'no message (button does nothing)'}", "what the app showed")

    with step("FAM-04"):
        # Phone is optional and (tester, 19 Oct) the app does not check its length: this step only
        # RECORDS what happens with a 7-digit number. A member saved this way is deleted at once.
        sheet.fill(sheet.NAME_HINT, name)                   # relationship was chosen in FAM-03
        short_phone = new_short_phone(FAMILY_SHORT_PHONE)  # e.g. 0300417 - new every run
        _note(short_phone, "short phone used")
        sheet.fill(sheet.PHONE_HINT, short_phone)
        sheet.tap_add()
        # Decide by what the screen shows, not by the green banner (it can vanish before we look):
        # an alert or error text = rejected; the form closing = saved.
        errors = sheet.error_texts()
        sheet.close_alert()
        short_saved = not errors and sheet.wait_closed(timeout=15)
        _screenshot(driver, f"after Add Member with phone {short_phone}")
        if short_saved:
            assert _listed_after_add(driver, family, name), \
                (f"Add New Member closed but '{name}' was NOT saved (not in the list, even after reopening it). "
                 f"Phone used: {short_phone}. See 'what the list shows' in the report")
            card = family.card_text(name)
            result = f"ACCEPTED: saved with a {len(short_phone)}-digit phone (no length check). Card: {card}"
            assert family.delete_member(name), f"Could not delete '{name}' (saved with the short phone)"
            name = new_test_name()                          # fresh name, so the old banner can't confuse FAM-05
            _note(name, "test member (after FAM-04)")
        else:
            result = "REJECTED: " + (" / ".join(errors) or "not saved, no message shown")
        _note(result, "short phone result")
        print(f"\nFAM-04 short phone {short_phone}: {result}")

    with step("FAM-05"):
        if short_saved:                                     # start again with a new, empty form
            assert family.open_add_sheet(), "'Add New Member' did not open"
            sheet.choose(FAMILY_RELATION)
            sheet.fill(sheet.NAME_HINT, name)
            sheet.fill(sheet.PHONE_HINT, FAMILY_PHONE)
        else:                                               # form still open: fix the phone
            sheet.refill(short_phone, FAMILY_PHONE)
        sheet.tap_add()
        assert sheet.added_message(name), f"No '{name} added to your family' message"
        assert sheet.wait_closed(), "Add New Member did not close after adding"
        assert _listed_after_add(driver, family, name), f"'{name}' not in the list after adding"
        assert family.count_badge() == before + 1, f"Count did not go up to {before + 1}"

    with step("FAM-06"):
        card = family.card_text(name)
        _note(card, "new member's card")
        for expected in (name, FAMILY_RELATION, FAMILY_GENDER, _shown_phone(FAMILY_PHONE)):
            assert expected in card, f"'{expected}' missing on the new member's card: {card}"

    with step("FAM-07"):
        restart_app(driver)
        open_test_doctor_summary(driver)
        assert section.has_member(name), f"'{name}' not under Appointment For on Booking Summary"
        relation = section.relation_of(name)
        assert relation == FAMILY_RELATION, f"Appointment For shows '{relation}' under {name}, expected {FAMILY_RELATION}"
        # Nothing is tapped here: nothing is booked.

    with step("FAM-08"):
        restart_app(driver)
        assert family.open(), "Friends & Family did not open"
        assert family.tap_bin(name), "'Delete Member' pop-up did not open"
        assert family.has_text(family.DELETE_QUESTION), "Delete question missing in the pop-up"
        family.cancel_delete()
        assert not family.is_visible(family.DELETE_TITLE, timeout=3), "Pop-up still open after CANCEL"
        assert family.has_member(name), f"'{name}' disappeared after CANCEL"
        assert family.count_badge() == before + 1, "Count changed after CANCEL"

    with step("FAM-09"):
        assert family.tap_bin(name), "'Delete Member' pop-up did not open"
        family.confirm_delete()
        assert family.is_visible(family.REMOVED_MSG, timeout=10), "No 'Family member removed' message"
        assert family.wait_gone(name), f"'{name}' still in the list after DELETE"
        assert family.count_badge() == before, f"Count did not go back to {before}"
        for member in FAMILY_MEMBERS:
            assert family.has_member(member), f"'{member}' missing after deleting the test member"

    with step("FAM-10"):
        restart_app(driver)
        open_test_doctor_summary(driver)
        assert section.has_member(FAMILY_MEMBERS[0]), "Appointment For did not load"
        assert not section.has_member(name), f"Deleted member '{name}' still under Appointment For"


@pytest.mark.family
@allure.title("FAM: add a family member from Booking Summary (Appointment For), then delete it")
def test_family_add_from_booking_summary(driver, family):
    name = new_test_name()
    _note(name, "test member")
    sheet = MemberSheet(driver)
    section = AppointmentFor(driver)

    with step("FAM-11"):
        open_test_doctor_summary(driver)
        assert section.open_add_sheet(), "'Add New Member' did not open from Appointment For"
        for relation in FAMILY_RELATIONS_BOOKING:
            assert sheet.chip(relation), f"Relationship '{relation}' missing"
        for gender in ("Male", "Female"):
            assert sheet.has_gender(gender), f"Gender '{gender}' missing"
        extra = [r for r in FAMILY_RELATIONS_PROFILE if r not in FAMILY_RELATIONS_BOOKING and sheet.chip(r)]
        _note(f"Relationships here that are not in FAMILY_RELATIONS_BOOKING: {extra or 'none'}", "relationships")
        sheet.tap_add()                                     # empty form
        alert = sheet.alert_text(timeout=8)
        assert FAMILY_FILL_ALERT in alert, f"Expected alert '{FAMILY_FILL_ALERT}', got '{alert}'"
        sheet.close_alert()
        assert sheet.is_open(timeout=5), "Add New Member closed after the alert"

    with step("FAM-12"):
        sheet.choose(FAMILY_BOOKING_RELATION)             # choices first: the keyboard can cover them
        sheet.choose_gender(FAMILY_BOOKING_GENDER)
        sheet.fill(sheet.NAME_HINT, name)
        sheet.tap_add()                                     # no phone: it is optional
        _note("yes" if sheet.added_message(name, timeout=5) else "no", "'added to your family' message shown")
        assert sheet.wait_closed(), "Add New Member did not close after adding"
        assert section.has_member(name), f"'{name}' not under Appointment For after adding"
        relation = section.relation_of(name)
        assert relation == FAMILY_BOOKING_RELATION, f"Shows '{relation}' under {name}, expected {FAMILY_BOOKING_RELATION}"
        _screenshot(driver, "Appointment For after adding (is the new member selected?)")
        # Book Appointment is NOT tapped: nothing is booked.

    with step("FAM-13"):
        restart_app(driver)
        assert family.open(), "Friends & Family did not open"
        assert family.has_member(name, timeout=10), f"'{name}' (added on Booking Summary) not in Friends & Family"
        card = family.card_text(name)
        _note(card, "new member's card")
        for expected in (name, FAMILY_BOOKING_RELATION, FAMILY_BOOKING_GENDER, FAMILY_DEFAULT_PHONE_SHOWN):
            assert expected in card, f"'{expected}' missing on the card: {card}"
        assert family.delete_member(name), f"'{name}' still in the list after DELETE"