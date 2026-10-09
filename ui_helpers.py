"""Pure helpers for the Streamlit chat client; kept importable without Streamlit."""

from __future__ import annotations

from typing import Any


MIN_PATIENT_ID = 1_000_000
MAX_PATIENT_ID = 99_999_999


def normalize_patient_id(value: str | int | None) -> int | None:
    """Accept only numeric patient IDs within the API's documented bounds."""
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    if not text.isdigit():
        return None
    parsed = int(text)
    return parsed if MIN_PATIENT_ID <= parsed <= MAX_PATIENT_ID else None


def latest_assistant_message(messages: Any) -> str:
    """Extract the newest assistant response without rendering arbitrary objects."""
    if not isinstance(messages, list):
        return "I couldn't find a response."
    for item in reversed(messages):
        if not isinstance(item, dict):
            continue
        role = item.get("type") or item.get("role")
        content = item.get("content")
        if role in {"ai", "assistant"} and isinstance(content, str) and content.strip():
            return content.strip()
    return "I couldn't find a response."


def escalation_details(payload: Any) -> dict[str, str] | None:
    """Return a bounded, validated escalation status block from an API response."""
    if not isinstance(payload, dict):
        return None
    value = payload.get("escalation")
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    case_id = value.get("case_id")
    trigger = value.get("trigger", "")
    allowed_statuses = {"pending", "acknowledged", "resolved", "cancelled", "failed"}
    if status not in allowed_statuses:
        return None
    if case_id is not None and not isinstance(case_id, str):
        return None
    if trigger is not None and not isinstance(trigger, str):
        return None
    result = {"status": status}
    if case_id:
        result["case_id"] = case_id[:64]
    if trigger:
        result["trigger"] = trigger[:80]
    return result
