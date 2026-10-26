"""Chat screen - the SAME screen in the doctor app (Marham Connect) and the patient app (Marham).
One chat per doctor + patient account (every booking of that account opens the same chat).
Locators from Appium Inspector + page source, 23 Oct 2026 (phone 720x1612).

Header   : back (clickable ViewGroup, top left), name TextView ('Momina Amir' / 'Dr. Unaiza Nisar Testing'),
           info icon (top right).
Messages : ScrollView [0,167][720,1455], newest at the BOTTOM. A message = clickable ViewGroup whose
           content-desc is the message text (its TextView child has the same text).
           Sent by me  = right side (ends at x 690, tick icon + time on its left).
           Received    = left side (starts at x 101, avatar, sender name above, time on its right).
           The time ('5:13 PM') is shown on the LAST message of a group only.
Input    : EditText 'Enter message' [104,1475][616,1547]; '+' (attach) on its left;
           on its right the MIC when the box is empty and SEND when text is typed (same place).
           -> send() only taps it after checking the box holds the message (never records a voice note).
Doctor app  : Appointments card button content-desc ', Chat'.
Patient app : Bookings card of the doctor -> chat icon (bottom right of the card).
Notification: 'Dr. Momina Testing has sent you a message' (patient app, when the doctor writes)."""
import datetime
import re
import time
import xml.etree.ElementTree as ET

from selenium.common.exceptions import WebDriverException

from pages.doctor_appointments_page import (DoctorAppointmentsPage, _buttons, _inside, _tap_box, clean,
                                            screen_nodes)

HINT = "Enter message"
TIME_RE = re.compile(r"^\d{1,2}:\d{2} [AP]M$")
LIST_TOP = 167                       # messages area starts below the header


def _root(driver):
    return ET.fromstring(driver.page_source.encode("utf-8"))


def _box(node):
    numbers = re.findall(r"-?\d+", node.get("bounds") or "")
    return tuple(int(v) for v in numbers) if len(numbers) == 4 else None


VOICE_RE = re.compile(r"^\d{1,2}:\d{2}$")       # voice note bubble: content-desc = its length '0:04'


class Message:
    """kind: 'text' (text = the message), 'voice' (text = length '0:04'), 'image' (text = '[image]')."""

    def __init__(self, text, box, time_text, kind="text"):
        self.text, self.box, self.time, self.kind = text, box, time_text, kind
        self.side = "received" if box[0] <= 120 else "sent"          # received bubbles start at x 101

    def seconds(self):
        """Voice note length in seconds ('0:04' -> 4), None for other kinds."""
        if self.kind != "voice":
            return None
        minutes, secs = self.text.split(":")
        return int(minutes) * 60 + int(secs)

    def label(self):
        return f"{self.side:<8} {self.time or '':>8}  {self.kind:<5} {self.text}"


def _stamp(node, parent, levels=4):
    """The time ('5:45 PM') of a message: a TextView child of one of the bubble's first ancestors."""
    for _ in range(levels):
        node = parent.get(node)
        if node is None:
            return ""
        for k in node:
            if k.get("class") == "android.widget.TextView" and TIME_RE.match(clean(k.get("text"))):
                return clean(k.get("text"))
    return ""


def messages(root):
    """Messages on screen, top to bottom.
    text  = clickable ViewGroup, content-desc = its text (TextView child with the same text)
    voice = clickable ViewGroup, content-desc '0:04' (play icon + TextView '0:04')
    image = clickable ViewGroup without content-desc holding a big ImageView (sent [210,1098][690,1418])"""
    parent = {k: p for p in root.iter() for k in p}
    found, seen = [], set()
    for n in root.iter():
        box = _box(n)
        if n.get("clickable") != "true" or n.get("class") != "android.view.ViewGroup" or not box or box[1] < LIST_TOP:
            continue
        desc = clean(n.get("content-desc"))
        if desc:
            texts = [clean(k.get("text")) for k in n.iter() if k.get("class") == "android.widget.TextView"]
            if desc not in texts:
                continue
            kind = "voice" if VOICE_RE.match(desc) else "text"
            found.append(Message(desc, box, _stamp(n, parent), kind))
            continue
        width = box[2] - box[0]
        pictures = [_box(k) for k in n.iter() if k.get("class") == "android.widget.ImageView" and _box(k)
                    and _box(k)[2] - _box(k)[0] >= 150 and _box(k)[3] - _box(k)[1] >= 100]
        if pictures and width < 600 and box not in seen:
            seen.add(box)
            found.append(Message("[image]", box, _stamp(n, parent), "image"))
    return sorted(found, key=lambda m: m.box[1])


class ChatPage:
    def __init__(self, driver):
        self.driver = driver

    # ---------- reading ----------
    def is_open(self, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self._input(_root(self.driver)) is not None:
                    return True
            except WebDriverException:
                pass
            time.sleep(1)
        return False

    @staticmethod
    def _input(root):
        return next((n for n in root.iter() if n.get("class") == "android.widget.EditText"), None)

    def header(self):
        """The name at the top of the chat."""
        for n in _root(self.driver).iter():
            box = _box(n)
            if n.get("class") == "android.widget.TextView" and clean(n.get("text")) and box and box[3] <= LIST_TOP:
                return clean(n.get("text"))
        return ""

    def messages(self):
        return messages(_root(self.driver))

    def find(self, text):
        return next((m for m in self.messages() if m.text == text), None)

    def wait_for(self, text, timeout=30):
        """The message with this text once it is on screen (scrolls to the bottom while waiting), else None."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                found = self.find(text)
                if found:
                    return found
                self.scroll_to_bottom()
            except WebDriverException:
                pass
            time.sleep(2)
        return None

    def scroll_to_bottom(self):
        size = self.driver.get_window_size()
        for _ in range(3):
            try:
                more = self.driver.execute_script("mobile: scrollGesture", {
                    "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3),
                    "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.45),
                    "direction": "down", "percent": 1.0})
            except WebDriverException:
                more = False
            if not more:
                return

    # ---------- sending ----------
    def send(self, text):
        """Type the text and tap SEND. Returns the texts in the box before and after tapping."""
        field = self.driver.find_elements("class name", "android.widget.EditText")
        assert len(field) == 1, f"Expected one message box on the chat screen, found {len(field)}"
        field[0].click()
        field[0].send_keys(text)
        time.sleep(1)
        root = _root(self.driver)
        box_node = self._input(root)
        typed = clean(box_node.get("text")) if box_node is not None else ""
        assert typed == text, f"Message box shows '{typed}' after typing '{text}' (not sent)"
        edit = _box(box_node)
        right = [(_box(n)) for n in root.iter() if n.get("clickable") == "true" and _box(n)
                 and _box(n)[0] >= edit[2] - 10 and _box(n)[1] < edit[3] and _box(n)[3] > edit[1]]
        assert right, "No SEND button right of the message box"
        _tap_box(self.driver, min(right, key=lambda b: b[0]))
        time.sleep(2)
        after = self._input(_root(self.driver))
        return typed, clean(after.get("text")) if after is not None else ""

    def go_back(self):
        self.driver.back()
        time.sleep(1)


def time_matches(stamp, now, minutes=2):
    """'5:13 PM' is within a few minutes of the phone time now."""
    if not TIME_RE.match(stamp or ""):
        return False
    shown = datetime.datetime.combine(now.date(), datetime.datetime.strptime(stamp, "%I:%M %p").time())
    return abs((shown - now).total_seconds()) <= minutes * 60


# ---------- doctor app: open the chat from an appointment card ----------
def open_doctor_chat(driver, tabs=("Upcoming", "Completed"), max_swipes=10):
    """Appointments -> first card with a 'Chat' button (Upcoming first, then Completed) -> Chat.
    Returns that card. (Every booking of the patient account opens the same chat.)"""
    page = DoctorAppointmentsPage(driver)
    assert page.open(), "Doctor app Appointments did not open"
    for tab in tabs:
        if page.tab(tab) is None:
            continue
        page.open_tab(tab)
        page.scroll_to_top()
        last = False                                   # the final scroll still moves the screen: read once more
        for _ in range(max_swipes + 1):
            nodes = screen_nodes(driver)
            for card, box in page.cards_on_screen(nodes):
                for label, button in _buttons(nodes):
                    if label == "Chat" and _inside(button, box):
                        _tap_box(driver, button)
                        return card
            if last:
                break
            last = not page._scroll("down", 0.4)
    return None


# ---------- patient app: open the chat from a Bookings card ----------
PATIENT_CHAT = "Chat with doctor"          # chat icon on a patient Bookings card (content-desc)


def chat_icon(root, doctor, status="SCHEDULED"):          # status None = any status
    """(card text, chat icon box) of the first Bookings card of this doctor with this status, or (None, None).
    Card = clickable ViewGroup, content-desc 'SCHEDULED, PAID, <i>, TODAY, 23, 05:40 PM, <i>, Dr. Momina Testing,
    Video Consultation, <i>, Patient Name: Momina Amir'; its child ViewGroup content-desc 'Chat with doctor'."""
    for card in root.iter():
        desc = clean(card.get("content-desc"))
        if doctor not in desc or (status and not desc.startswith(status)):
            continue
        icon = next((n for n in card.iter() if n is not card and n.get("clickable") == "true"
                     and clean(n.get("content-desc")) == PATIENT_CHAT), None)
        if icon is not None:
            return desc, _box(icon)
    return None, None


def notification_texts(driver, wanted, seconds=20):
    """Open the notification shade and wait for a text containing every part of `wanted`.
    Returns (matching text or '', every text seen). Closes the shade again."""
    driver.open_notifications()
    seen, match, end = [], "", time.time() + seconds
    try:
        while time.time() < end and not match:
            time.sleep(1.5)
            try:
                texts = [clean(n.get("text")) for n in _root(driver).iter() if clean(n.get("text"))]
            except WebDriverException:
                continue
            seen += [t for t in texts if t not in seen]
            match = next((t for t in texts if all(w in t for w in wanted)), "")
    finally:
        driver.back()
        time.sleep(1)
    return match, seen