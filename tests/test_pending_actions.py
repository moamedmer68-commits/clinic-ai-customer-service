import json

import pandas as pd
import pytest

import support.pending_actions as pending


def _book_payload():
    return {"doctor_name": "john doe", "desired_date": "12-10-2026 09:00"}


def test_create_pending_action_stores_exact_details_without_mutating_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))

    action, created = pending.create_pending_action("thread-a", "book", _book_payload())
    retrieved = pending.get_pending_action("thread-a")

    assert created is True
    assert action["status"] == "pending"
    assert retrieved["action_id"] == action["action_id"]
    assert retrieved["payload"] == _book_payload()
    assert retrieved["operation"] == "book"
    assert not (tmp_path / "doctor_availability.csv").exists()


def test_one_pending_action_per_thread_and_actions_are_session_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))

    first, created = pending.create_pending_action("thread-a", "book", _book_payload())
    duplicate, duplicate_created = pending.create_pending_action(
        "thread-a", "cancel", {"doctor_name": "jane smith", "date": "12-10-2026 11:00"}
    )
    other_thread, other_created = pending.create_pending_action(
        "thread-b", "cancel", {"doctor_name": "jane smith", "date": "12-10-2026 11:00"}
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate["action_id"] == first["action_id"]
    assert duplicate["operation"] == "book"
    assert other_created is True
    assert other_thread["action_id"] != first["action_id"]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("YES", "affirmative"),
        ("Yes!", "affirmative"),
        ("تمام", "ambiguous"),
        ("أيوه", "affirmative"),
        ("نعم", "affirmative"),
        ("NO", "negative"),
        ("لا", "negative"),
        ("yes please", "ambiguous"),
        ("CONFIRM", "ambiguous"),
        ("cancel request", "ambiguous"),
        ("yes, but make it tomorrow", "ambiguous"),
        ("yes and also cancel another appointment", "ambiguous"),
        ("I think so", "ambiguous"),
        ("", "ambiguous"),
    ],
)
def test_confirmation_classifier_accepts_only_exact_phrases(message, expected):
    assert pending.classify_confirmation(message) == expected


def test_pending_action_can_be_claimed_only_once_and_finalized(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    created, _ = pending.create_pending_action("thread-a", "book", _book_payload())

    claimed = pending.claim_pending_action("thread-a")
    duplicate_claim = pending.claim_pending_action("thread-a")

    assert claimed["action_id"] == created["action_id"]
    assert claimed["status"] == "pending"
    assert duplicate_claim is None
    assert pending.finish_pending_action(created["action_id"], "executed", "Successfully done")
    assert pending.get_pending_action("thread-a") is None


def test_expired_action_cannot_be_confirmed(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    clock = {"value": 1000}
    monkeypatch.setattr(pending, "_now", lambda: clock["value"])
    created, _ = pending.create_pending_action("thread-a", "book", _book_payload(), ttl_seconds=60)
    assert pending.get_pending_action("thread-a") is not None

    clock["value"] = 1061
    assert pending.get_pending_action("thread-a") is None
    connection = pending._connect()
    try:
        row = connection.execute(
            "SELECT status FROM pending_appointment_actions WHERE action_id = ?",
            (created["action_id"],),
        ).fetchone()
        assert row["status"] == "expired"
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        ("book", {"doctor_name": "unknown doctor", "desired_date": "12-10-2026 09:00"}),
        ("book", {"doctor_name": "john doe", "desired_date": "32-10-2026 09:00"}),
        ("cancel", {"doctor_name": "john doe", "date": "12-10-2026"}),
        ("reschedule", {"doctor_name": "john doe", "old_date": "12-10-2026 09:00", "new_date": "12-10-2026 09:00"}),
    ],
)
def test_invalid_action_payload_is_rejected(tmp_path, monkeypatch, operation, payload):
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    with pytest.raises(ValueError):
        pending.create_pending_action("thread-a", operation, payload)
    assert pending.get_pending_action("thread-a") is None


def test_prepare_tool_creates_pending_proposal_and_explicitly_says_no_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    prepare = pending.build_prepare_tool("thread-a")

    result = prepare.invoke({
        "operation": "book",
        "doctor_name": "john doe",
        "appointment_date": "12-10-2026 09:00",
    })

    assert "NO APPOINTMENT CHANGE HAS BEEN MADE" in result
    assert "YES" in result
    stored = pending.get_pending_action("thread-a")
    assert stored["payload"] == _book_payload()
