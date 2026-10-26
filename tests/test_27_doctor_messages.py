"""Doctor <-> patient CHAT, checked in BOTH apps.                       pytest -m doctor_messages -s
1. Doctor app: Appointments -> card with 'Chat' -> sends 'AT doctor <time>'  -> shown on the right, time correct.
2. Phone notification for the patient: 'Dr. Momina Testing has sent you a message'.
3. Patient app: Bookings -> SCHEDULED card of the test doctor -> chat icon -> the doctor's message is shown
   on the LEFT (received). Then the patient sends 'AT patient <time>' -> shown on the right, below it.
4. Doctor app (fresh start): the patient's message is shown on the LEFT, below the doctor's message.
5. Patient app (fresh start): both messages still there, in the same order.
Nothing is deleted (the app cannot delete chat messages): only two short 'AT ...' texts are sent per run.
DMSG-08: the patient chat header must show the doctor's CURRENT name (bug reported 23 Oct 2026: old name shown).
Patient side opens the chat from a SCHEDULED booking (else any booking card with 'Chat with doctor'; none -> skipped)."""
import contextlib
import datetime

import allure
import pytest

from doctor_test_data import PATIENT_APP_DOCTOR_NAME
from pages.chat_page import HINT, notification_texts, time_matches
from utils.chat_open import doctor_chat as _doctor_chat, patient_chat as _patient_chat
from utils.doctor_app import to_doctor_app
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_messages]

NOTIFICATION = "has sent you a message"


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _now(driver):
    return datetime.datetime.strptime(driver.get_device_time("YYYY-MM-DD HH:mm:ss"), "%Y-%m-%d %H:%M:%S")


@contextlib.contextmanager
def _soft(failures, label):
    try:
        yield
    except AssertionError as exc:
        failures.append(f"{label}: {exc}")


def _show(chat, name):
    shown = chat.messages()
    _note("\n".join(m.label() for m in shown) or "no messages", name)
    return shown


def _wait_received(driver, open_chat, text, who):
    """Wait for `text` as a RECEIVED message; reopen the chat once if it does not arrive."""
    chat = open_chat(driver)
    found = chat.wait_for(text, timeout=30)
    if not found:
        chat = open_chat(driver)
        found = chat.wait_for(text, timeout=30)
    shown = _show(chat, f"{who} chat")
    assert found, f"{who} chat: '{text}' did not arrive within 60 s. Last messages: " + \
                  "; ".join(m.label() for m in shown[-4:])
    assert found.side == "received", f"{who} chat: '{text}' is shown on the {found.side} side, expected received (left)"
    return chat


def _check_sent(chat, text, now, who):
    found = chat.wait_for(text, timeout=15)
    shown = _show(chat, f"{who} chat after sending")
    assert found, f"{who}: sent '{text}' but it is not in the chat. Last messages: " + \
                  "; ".join(m.label() for m in shown[-4:])
    assert found.side == "sent", f"{who}: own message '{text}' is shown on the {found.side} side, expected right"
    assert shown and shown[-1].text == text, f"{who}: own message is not the newest one (last is '{shown[-1].text}')"
    assert time_matches(found.time, now), f"{who}: message time '{found.time}', phone time {now:%I:%M %p}"


def _order(chat, first, second, who):
    shown = [m.text for m in chat.messages()]
    assert first in shown and second in shown, f"{who} chat: missing {[t for t in (first, second) if t not in shown]}"
    assert shown.index(first) < shown.index(second), f"{who} chat: '{second}' is shown ABOVE '{first}'"


@pytest.mark.flaky(reruns=0)
@allure.title("DMSG: doctor and patient chat - each message reaches the other app")
def test_chat_both_ways(driver):
    stamp = _now(driver)
    doctor_text = f"AT doctor {stamp:%H%M%S}"
    patient_text = f"AT patient {stamp:%H%M%S}"
    print(f"\nPHONE TIME {stamp:%a %d %b %I:%M %p} | doctor sends '{doctor_text}' | patient sends '{patient_text}'")
    failures = []

    with step("DMSG-01"):
        chat = _doctor_chat(driver)
        _note(chat.header(), "doctor chat header (patient)")
        _show(chat, "doctor chat before")

    with step("DMSG-02"):
        now = _now(driver)
        typed, left = chat.send(doctor_text)
        assert left in ("", HINT), f"Doctor: message box still shows '{left}' after SEND"
        _check_sent(chat, doctor_text, now, "Doctor")

    with _soft(failures, "DMSG-03"), step("DMSG-03"):
        match, seen = notification_texts(driver, [PATIENT_APP_DOCTOR_NAME, NOTIFICATION])
        _note("\n".join(seen), "notification shade")
        assert match, f"No phone notification '{PATIENT_APP_DOCTOR_NAME} {NOTIFICATION}' within 20 s"

    with step("DMSG-04"):
        chat = _wait_received(driver, _patient_chat, doctor_text, "Patient")
        header = chat.header()
        _note(header, "patient chat header (doctor)")

    with _soft(failures, "DMSG-08"), step("DMSG-08"):            # BUG reported 23 Oct 2026: old name shown
        assert header == PATIENT_APP_DOCTOR_NAME, \
            f"Patient chat header shows '{header}', the doctor's current name is '{PATIENT_APP_DOCTOR_NAME}' (known bug)"

    with step("DMSG-05"):
        now = _now(driver)
        typed, left = chat.send(patient_text)
        assert left in ("", HINT), f"Patient: message box still shows '{left}' after SEND"
        _check_sent(chat, patient_text, now, "Patient")
        _order(chat, doctor_text, patient_text, "Patient")

    with step("DMSG-06"):
        chat = _wait_received(driver, _doctor_chat, patient_text, "Doctor")
        mine = chat.find(doctor_text)
        assert mine and mine.side == "sent", f"Doctor chat: own message '{doctor_text}' not on the right after reopening"
        _order(chat, doctor_text, patient_text, "Doctor")

    with _soft(failures, "DMSG-07"), step("DMSG-07"):
        chat = _patient_chat(driver)
        chat.wait_for(patient_text, timeout=20)
        shown = {m.text: m.side for m in _show(chat, "patient chat after restart")}
        assert shown.get(doctor_text) == "received" and shown.get(patient_text) == "sent", \
            f"Patient chat after restart: doctor message {shown.get(doctor_text)}, own message {shown.get(patient_text)}"
        _order(chat, doctor_text, patient_text, "Patient (after restart)")

    to_doctor_app(driver)
    assert not failures, "Chat problems:\n" + "\n".join(failures)