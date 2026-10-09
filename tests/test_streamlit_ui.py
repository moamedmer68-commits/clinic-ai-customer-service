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


def test_streamlit_ui_rejects_invalid_patient_id_without_api_call(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: calls.append((args, kwargs)))

    at = AppTest.from_file(str(APP_PATH)).run()
    at.text_input[0].set_value("not-numeric")
    at.chat_input[0].set_value("Hello")
    at.run()

    assert not at.exception
    assert calls == []
    assert any("numeric patient ID" in item.value for item in at.error)


def test_streamlit_ui_renders_response_and_pending_escalation(monkeypatch):
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
    at = AppTest.from_file(str(APP_PATH)).run()
    at.text_input[0].set_value("1234567")
    at.chat_input[0].set_value("Please connect me with a human")
    at.run()

    assert not at.exception
    assert len(calls) == 1
    assert calls[0][1]["json"]["id_number"] == 1234567
    assert calls[0][1]["timeout"] >= 5
    assert any("I have created a support case." in item.value for item in at.markdown)
    assert any("HND-20261009-ABC123" in item.value for item in at.info)
    assert any("No human response has been received yet" in item.value for item in at.info)


def test_streamlit_ui_new_conversation_clears_transcript():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.session_state["transcript"] = [{"role": "assistant", "content": "previous message"}]
    at.run()
    assert any("previous message" in item.value for item in at.markdown)

    old_session = at.session_state["session_id"]
    at.button[0].click().run()

    assert at.session_state["transcript"] == []
    assert at.session_state["session_id"] != old_session
    assert not at.exception
