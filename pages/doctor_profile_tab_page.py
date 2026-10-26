"""Doctor app (Marham Connect) - Profile tab and View Profile. READ-ONLY: nothing here taps Log Out,
an Edit button or a Save button. Locators from Appium Inspector + page source, 22 Oct 2026 (app 13.8).
(The patient app already has pages/doctor_profile_page.py, hence this file's name.)

Profile tab: title 'Profile', then name, specialty, 'Verified Profile', '10 Yrs' / 'Experience', '4.9' / 'Rating',
sections GENERAL / PRACTICE MANAGEMENT / LEGAL / APP SETTINGS. Each row is a clickable ViewGroup with
content-desc '<icon>, <label>, <icon>'; Log Out has content-desc 'Log Out'.
View Profile: 'Personal Information' with label TextViews, each followed by a DISABLED EditText holding the value."""
import time
import xml.etree.ElementTree as ET

from selenium.common.exceptions import WebDriverException

from pages.base_page import BasePage
from pages.doctor_appointments_page import _tap_box, clean
from pages.doctor_home_page import DoctorHomePage, exact

MENU = ("View Profile", "Manage Locations", "Manage Leaves", "Scheduler Settings", "Reviews",
        "Billing & Payment", "Work Policy", "Agreement", "Privacy & Security", "Help & Support")
SECTIONS = ("GENERAL", "PRACTICE MANAGEMENT", "LEGAL", "APP SETTINGS")
NEVER_TAP = ("Log Out",)


def _box(node):
    import re
    numbers = re.findall(r"-?\d+", node.get("bounds") or "")
    return tuple(int(v) for v in numbers) if len(numbers) == 4 else None


def _row_label(desc):
    """', Manage Locations, ' (icons removed) -> 'Manage Locations'."""
    parts = [p.strip() for p in clean(desc).split(",") if p.strip()]
    return parts[0] if len(parts) == 1 else ""


def _scroll(driver, direction, percent=0.7):
    size = driver.get_window_size()
    try:
        return driver.execute_script("mobile: scrollGesture", {
            "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3),
            "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5),
            "direction": direction, "percent": percent})
    except WebDriverException:
        return False


def _texts(page_source):
    root = ET.fromstring(page_source.encode("utf-8"))
    return [clean(n.get("text")) for n in root.iter()
            if n.get("class") == "android.widget.TextView" and clean(n.get("text"))]


class DoctorProfileTabPage(BasePage):
    TITLE = exact("Profile")

    def open(self):
        DoctorHomePage(self.driver).open_tab("Profile")
        opened = self.is_visible(self.TITLE, timeout=self.TIMEOUT) and self.is_visible(exact("GENERAL"), timeout=10)
        self.scroll_to_top()
        return opened

    def scroll_to_top(self):
        for _ in range(6):
            if not _scroll(self.driver, "up", 1.0):
                break

    def header(self):
        """{'name', 'specialty', 'verified', 'experience', 'rating'} from the top of the Profile tab."""
        self.scroll_to_top()
        texts = _texts(self.driver.page_source)
        top = texts[texts.index("Profile") + 1:] if "Profile" in texts else texts
        def before(word):
            return top[top.index(word) - 1] if word in top and top.index(word) > 0 else ""
        return {"name": top[0] if top else "", "specialty": top[1] if len(top) > 1 else "",
                "verified": "Verified Profile" in top, "experience": before("Experience"),
                "rating": before("Rating")}

    def rows(self, max_swipes=6):
        """Labels of every row (scrolls down, then back up), plus 'Log Out' and the section titles seen."""
        rows, sections = [], []
        last = False                                   # the final scroll still moves the screen: read once more
        for _ in range(max_swipes + 1):
            root = ET.fromstring(self.driver.page_source.encode("utf-8"))
            for n in root.iter():
                label = _row_label(n.get("content-desc")) if n.get("clickable") == "true" else ""
                if n.get("content-desc") == "Log Out":
                    label = "Log Out"
                if label and n.get("class") == "android.view.ViewGroup" and label not in rows:
                    rows.append(label)
                text = clean(n.get("text"))
                if text in SECTIONS and text not in sections:
                    sections.append(text)
            if last:
                break
            last = not _scroll(self.driver, "down")
        self.scroll_to_top()
        return rows, sections

    def open_row(self, label, max_swipes=6):
        """Tap one row (never Log Out)."""
        assert label not in NEVER_TAP, f"Refused to tap '{label}'"
        self.scroll_to_top()
        last = False                                   # the final scroll still moves the screen: read once more
        for _ in range(max_swipes + 1):
            root = ET.fromstring(self.driver.page_source.encode("utf-8"))
            for n in root.iter():
                box = _box(n)
                if (n.get("clickable") == "true" and _row_label(n.get("content-desc")) == label
                        and box and box[3] - box[1] > 60):          # fully on screen (a row is 120 px high)
                    _tap_box(self.driver, box)
                    time.sleep(1)
                    return
            if last:
                break
            last = not _scroll(self.driver, "down", 0.4)
        raise AssertionError(f"Row '{label}' not found on the Profile tab")


class ViewProfilePage(BasePage):
    TITLE = exact("View Profile")

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def fields(self, max_swipes=3):
        """{label: (value, editable)}: each label TextView is followed by its EditText (disabled = read-only)."""
        found = {}
        last = False                                   # the final scroll still moves the screen: read once more
        for _ in range(max_swipes + 1):
            root = ET.fromstring(self.driver.page_source.encode("utf-8"))
            label = None
            for n in root.iter():
                cls, text = n.get("class"), clean(n.get("text"))
                if cls == "android.widget.TextView" and text:
                    label = text
                elif cls == "android.widget.EditText" and label:
                    found.setdefault(label, (text, n.get("enabled") == "true"))
                    label = None
            if last:
                break
            last = not _scroll(self.driver, "down")
        return found

    def go_back(self):
        self.driver.back()