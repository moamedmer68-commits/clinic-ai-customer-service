import pytest

from ui_helpers import escalation_details, latest_assistant_message, normalize_patient_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234567", 1234567),
        (1234567, 1234567),
        (" 7654321 ", 7654321),
        ("123", None),
        ("100000000", None),
        ("12x4567", None),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_normalize_patient_id_enforces_api_bounds(value, expected):
    assert normalize_patient_id(value) == expected


def test_latest_assistant_message_skips_non_string_and_non_assistant_messages():
    assert latest_assistant_message([
        {"type": "ai", "content": "old"},
        {"type": "human", "content": "question"},
        {"type": "ai", "content": {"unexpected": "object"}},
        {"type": "ai", "content": "latest response"},
    ]) == "latest response"


def test_latest_assistant_message_has_safe_fallback():
    assert latest_assistant_message(None) == "I couldn't find a response."
    assert latest_assistant_message([{"type": "human", "content": "hello"}]) == "I couldn't find a response."


def test_escalation_details_accepts_only_known_status_and_bounds_strings():
    assert escalation_details({
        "escalation": {"status": "pending", "case_id": "HND-20261009-ABC123", "trigger": "unresolved_faq"}
    }) == {
        "status": "pending",
        "case_id": "HND-20261009-ABC123",
        "trigger": "unresolved_faq",
    }
    assert escalation_details({"escalation": {"status": "unknown", "case_id": "HND-1"}}) is None
    assert escalation_details({"escalation": {"status": "pending", "case_id": 123}}) is None
    assert escalation_details({"escalation": None}) is None
