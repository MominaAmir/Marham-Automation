"""Doctor app (Marham Connect) - Pending Confirmations (Home > Quick Access tile).
Locators from Appium Inspector + page source, 22 Oct 2026 (app 13.8).

A card has NO content-desc (unlike the Appointments cards). It is a ViewGroup whose own children are:
  TextViews  'MA' (initials), 'Momina Amir' (account), 'Booked for Tooba' (only for a family member),
             'Video Consultation' or '13-b Hospital', 'Thu, Oct 22', '02:10 PM'
  buttons    clickable ViewGroups with content-desc '<icon>, Accept' and '<icon>, Reschedule'.
Accept confirms at once (no 'are you sure?'): a banner "Appointment confirmed successfully" (with an X,
it goes away by itself) and the card leaves the list ("All caught up! / No pending confirmations" when empty).
SAFETY: only Accept inside the chosen card is ever tapped. Reschedule is never tapped."""
import datetime
import re
import time
import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException

from pages.base_page import BasePage
from pages.doctor_appointments_page import _inside, _tap_box, clean, label_of, screen_nodes
from pages.doctor_home_page import DoctorHomePage, exact

UI = AppiumBy.ANDROID_UIAUTOMATOR
TILE = (UI, 'new UiSelector().descriptionContains("Pending Confirmations")')   # Home > Quick Access
TILE_COUNT_RE = re.compile(r"(\d+)\s*,\s*Pending Confirmations")
DATE_RE = re.compile(r"^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$")            # Thu, Oct 22
TIME_RE = re.compile(r"^\d{1,2}:\d{2} [AP]M$")                              # 02:10 PM
INITIALS_RE = re.compile(r"^[A-Z]{1,3}$")                                   # MA


def _box(node):
    numbers = re.findall(r"-?\d+", node.get("bounds") or "")
    return tuple(int(v) for v in numbers) if len(numbers) == 4 else None


class PendingCard:
    """One pending card. Its parts are found by their shape (date, time, 'Booked for ...'), not position."""

    def __init__(self, texts, buttons, box):
        self.texts, self.buttons, self.box = texts, buttons, box
        rest = [t for t in texts if not INITIALS_RE.match(t)]
        self.date = next((t for t in rest if DATE_RE.match(t)), "")             # Thu, Oct 22
        self.time = next((t for t in rest if TIME_RE.match(t)), "")             # 02:10 PM
        self.booked_for = next((t[len("Booked for "):] for t in rest if t.startswith("Booked for ")), "")
        others = [t for t in rest if t not in (self.date, self.time) and not t.startswith("Booked for ")]
        self.patient = others[0] if others else ""                              # Momina Amir (the account)
        self.location = others[1] if len(others) > 1 else ""                    # Video Consultation / 13-b Hospital

    @property
    def key(self):
        return self.date, self.time, self.patient, self.booked_for, self.location

    @property
    def month_day(self):
        """'Thu, Oct 22' -> 'Oct 22' (the Appointments list shows 'Oct 22, 2026')."""
        return self.date.split(", ", 1)[-1]

    def when(self, year):
        return datetime.datetime.strptime(f"{self.month_day} {year} {self.time}", "%b %d %Y %I:%M %p")

    def is_slot(self, month_day, time_text):
        return self.month_day == month_day and self.time == time_text

    def label(self):
        who = f"{self.patient} (for {self.booked_for})" if self.booked_for else self.patient
        return f"{who} | {self.date} {self.time} | {self.location} | buttons: {self.buttons}"


def pending_cards(page_source):
    """Cards in this page source: every ViewGroup that has an 'Accept' button as its own child."""
    root = ET.fromstring(page_source.encode("utf-8"))
    cards = []
    for parent in root.iter():
        kids = list(parent)
        buttons = [label_of(k.get("content-desc")) for k in kids
                   if k.get("clickable") == "true" and label_of(k.get("content-desc"))]
        if "Accept" not in buttons:
            continue
        texts = [clean(k.get("text")) for k in kids if k.get("class") == "android.widget.TextView"]
        cards.append(PendingCard([t for t in texts if t], buttons, _box(parent)))
    return cards


class PendingConfirmationsPage(BasePage):
    TITLE = exact("Pending Confirmations")
    EMPTY = exact("All caught up!")                     # + "No pending confirmations" when the list is empty

    # ---------- Home tile ----------
    def tile_count(self):
        """Number on the Home Quick Access tile ('<icon>, 1, Pending Confirmations' -> 1); None if no number."""
        for n in screen_nodes(self.driver):
            found = TILE_COUNT_RE.search(n["desc"])
            if found:
                return int(found.group(1))
        return None

    def open(self):
        """From Home: tap the Quick Access tile. True when the screen is open."""
        home = DoctorHomePage(self.driver)
        if not home.is_loaded(timeout=5):
            home.open_tab("Home")
            home.is_loaded()
        self.tap(TILE)
        opened = self.is_visible(self.TITLE, timeout=self.TIMEOUT)
        time.sleep(1.5)                                     # the cards come a moment after the title
        return opened

    def is_open(self, timeout=3):
        return self.is_visible(self.TITLE, timeout=timeout)

    # ---------- reading ----------
    def _scroll(self, direction, percent=0.6):
        size = self.driver.get_window_size()
        try:
            return self.driver.execute_script("mobile: scrollGesture", {
                "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5),
                "direction": direction, "percent": percent})
        except WebDriverException:
            return False

    def scroll_to_top(self):
        for _ in range(8):
            if not self._scroll("up", 1.0):
                break

    def cards(self, max_swipes=8):
        """Every pending card (scrolls down, then back to the top)."""
        found = {}
        for _ in range(max_swipes):
            for card in pending_cards(self.driver.page_source):
                found.setdefault(card.key, card)
            if not self._scroll("down"):
                break
        self.scroll_to_top()
        return list(found.values())

    def find(self, month_day, time_text, max_swipes=8):
        """The card for this slot ('Oct 22', '02:10 PM') as it is on screen now, or None."""
        self.scroll_to_top()
        for _ in range(max_swipes):
            for card in pending_cards(self.driver.page_source):
                if card.is_slot(month_day, time_text):
                    return card
            if not self._scroll("down", 0.4):
                break
        return None

    # ---------- the one action ----------
    def accept(self, card):
        """Tap 'Accept' inside this card (scrolls to it first). Returns the texts that appeared after the
        tap (the 'appointment confirmed' pop-up). Nothing else is ever tapped."""
        shown = self.find(card.month_day, card.time)
        assert shown, f"Pending card not on screen any more: {card.label()}"
        nodes = screen_nodes(self.driver)
        before = {n["text"] for n in nodes if n["text"]}
        accept = [n["box"] for n in nodes if n["clickable"] and label_of(n["desc"]) == "Accept"
                  and shown.box and _inside(n["box"], shown.box)]
        assert len(accept) == 1, f"Expected one Accept button inside {card.label()}, found {len(accept)}"
        _tap_box(self.driver, accept[0])
        new = []
        end = time.time() + 5
        while time.time() < end:                           # read for 5 s: the banner only shows for a moment
            time.sleep(0.7)
            try:
                now = [n["text"] for n in screen_nodes(self.driver) if n["text"]]
            except WebDriverException:
                continue
            new += [t for t in now if t not in before and t not in new]
        return new