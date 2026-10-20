from pathlib import Path

import requests
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_ui.py"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _authenticated_app():
    at = AppTest.from_file(str(APP_PATH))
    at.session_state["auth_token"] = "fake-bearer-token"
    at.session_state["patient_profile"] = {
        "status": "approved",
        "patient_id": "12345678",
        "full_name": "Test Patient",
    }
    return at


def test_streamlit_ui_shows_registration_and_login_before_authentication(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: calls.append((args, kwargs)))

    at = AppTest.from_file(str(APP_PATH)).run()

    assert not at.exception
    assert any("Create account" in item.label for item in at.tabs)
    assert any("Sign in" in item.label for item in at.tabs)
    assert calls == []
    assert not any("Demo Patient ID" in item.label for item in at.text_input)


def test_registration_posts_fields_and_never_displays_a_patient_id_before_approval(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"status": "pending_review"}, 202)

    monkeypatch.setattr(requests, "post", fake_post)
    at = AppTest.from_file(str(APP_PATH)).run()

    # Registration inputs are rendered before login inputs in the first tab.
    at.text_input[0].set_value("Test Patient")
    at.text_input[1].set_value("patient@example.test")
    at.text_input[2].set_value("+201000000000")
    at.text_input[3].set_value("A-long-test-password-123")
    at.button[0].click().run()

    assert not at.exception
    assert len(calls) == 1
    assert calls[0][0].endswith("/patients/register")
    assert calls[0][1]["json"]["full_name"] == "Test Patient"
    assert calls[0][1]["json"]["email"] == "patient@example.test"
    assert calls[0][1]["json"]["phone"] == "+201000000000"
    assert calls[0][1]["json"]["password"] == "A-long-test-password-123"
    assert any("Registration received" in item.value for item in at.success)
    assert not any("Patient ID" in item.value for item in at.markdown)


def test_login_stores_issued_patient_profile_and_bearer_token(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({
            "access_token": "server-issued-token",
            "token_type": "bearer",
            "patient": {
                "status": "approved",
                "patient_id": "12345678",
                "full_name": "Test Patient",
            },
        })

    monkeypatch.setattr(requests, "post", fake_post)
    at = AppTest.from_file(str(APP_PATH)).run()

    # Inputs 4 and 5 belong to the sign-in form.
    at.text_input[4].set_value("patient@example.test")
    at.text_input[5].set_value("A-long-test-password-123")
    at.button[1].click().run()

    assert not at.exception
    assert calls[0][0].endswith("/patients/login")
    assert at.session_state["auth_token"] == "server-issued-token"
    assert at.session_state["patient_profile"]["patient_id"] == "12345678"


def test_chat_uses_server_issued_patient_id_and_bearer_token(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({
            "session_id": "test-session",
            "messages": [{"type": "ai", "content": "I have created a support case."}],
            "escalation": {
                "status": "pending",
                "case_id": "HND-20261009-ABC123",
                "trigger": "human_requested",
            },
        })

    monkeypatch.setattr(requests, "post", fake_post)
    at = _authenticated_app().run()
    at.chat_input[0].set_value("Please connect me with a human")
    at.run()

    assert not at.exception
    assert len(calls) == 1
    assert calls[0][0].endswith("/execute")
    assert calls[0][1]["json"]["id_number"] == 12345678
    assert calls[0][1]["headers"]["Authorization"] == "Bearer fake-bearer-token"
    assert calls[0][1]["timeout"] >= 5
    assert any("I have created a support case." in item.value for item in at.markdown)
    assert any("HND-20261009-ABC123" in item.value for item in at.info)
    assert any("No human response has been received yet" in item.value for item in at.info)


def test_streamlit_ui_new_conversation_clears_transcript():
    at = _authenticated_app()
    at.session_state["transcript"] = [{"role": "assistant", "content": "previous message"}]
    at = at.run()
    assert any("previous message" in item.value for item in at.markdown)

    old_session = at.session_state["session_id"]
    at.button[0].click().run()

    assert at.session_state["transcript"] == []
    assert at.session_state["session_id"] != old_session
    assert not at.exception


def test_streamlit_ui_can_switch_to_arabic():
    at = AppTest.from_file(str(APP_PATH)).run()
    assert not at.exception
    at.selectbox[0].select(at.selectbox[0].options[1]).run()
    assert not at.exception
    assert at.session_state["language"] == at.selectbox[0].options[1]
