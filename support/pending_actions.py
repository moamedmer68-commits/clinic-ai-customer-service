"""Deterministic, session-scoped appointment mutation confirmation.

The LLM may prepare an exact action, but it never executes an appointment mutation
directly. A pending action is claimed and executed by the API only after an exact
affirmative message arrives in the same patient/session thread.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from langchain_core.tools import tool

ALLOWED_DOCTORS = {
    "kevin anderson", "robert martinez", "susan davis", "daniel miller",
    "sarah wilson", "michael green", "lisa brown", "jane smith",
    "emily johnson", "john doe",
}
DEFAULT_TTL_SECONDS = 900
VALID_OPERATIONS = {"book", "cancel", "reschedule"}
TERMINAL_STATUSES = {"executed", "cancelled", "failed", "expired"}


def _database_path() -> Path:
    path = Path(os.getenv("PENDING_ACTION_DB_PATH", "data/pending_actions.sqlite3")).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_database_path()), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_appointment_actions (
            action_id TEXT PRIMARY KEY,
            thread_ref TEXT NOT NULL,
            operation TEXT NOT NULL CHECK(operation IN ('book', 'cancel', 'reschedule')),
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'executed', 'cancelled', 'failed', 'expired')),
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            outcome TEXT
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pending_actions_thread_status "
        "ON pending_appointment_actions(thread_ref, status, expires_at)"
    )
    return connection


@contextmanager
def _database():
    connection = _connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _validate_datetime(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a date and time in DD-MM-YYYY HH:MM format")
    try:
        return datetime.strptime(value.strip(), "%d-%m-%Y %H:%M").strftime("%d-%m-%Y %H:%M")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a real date and time in DD-MM-YYYY HH:MM format") from exc


def validate_action(operation: str, payload: dict[str, Any]) -> dict[str, str]:
    """Normalize a pending action and reject unknown or incomplete mutation details."""
    if operation not in VALID_OPERATIONS:
        raise ValueError("Unsupported appointment action")
    doctor_name = payload.get("doctor_name")
    if not isinstance(doctor_name, str) or doctor_name.strip().casefold() not in ALLOWED_DOCTORS:
        raise ValueError("Select a supported doctor name")
    normalized: dict[str, str] = {"doctor_name": doctor_name.strip().casefold()}
    if operation in {"book", "cancel"}:
        field_name = "desired_date" if operation == "book" else "date"
        normalized[field_name] = _validate_datetime(payload.get(field_name), field_name)
    else:
        normalized["old_date"] = _validate_datetime(payload.get("old_date"), "old_date")
        normalized["new_date"] = _validate_datetime(payload.get("new_date"), "new_date")
        if normalized["old_date"] == normalized["new_date"]:
            raise ValueError("The new appointment time must differ from the current time")
    return normalized


def create_pending_action(
    thread_ref: str,
    operation: str,
    payload: dict[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> tuple[dict[str, Any], bool]:
    """Create one pending action per conversation, without performing the mutation."""
    if not isinstance(thread_ref, str) or not thread_ref.strip():
        raise ValueError("A session-scoped thread reference is required")
    normalized = validate_action(operation, payload)
    now = _now()
    ttl = max(60, min(int(ttl_seconds), 3600))
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))

    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE pending_appointment_actions SET status='expired', outcome='Confirmation expired' "
            "WHERE status='pending' AND expires_at <= ?",
            (now,),
        )
        existing = connection.execute(
            """
            SELECT * FROM pending_appointment_actions
            WHERE thread_ref = ? AND status IN ('pending', 'processing')
            ORDER BY created_at DESC LIMIT 1
            """,
            (thread_ref,),
        ).fetchone()
        if existing is not None:
            return dict(existing), False

        action_id = "PA-" + uuid4().hex[:16].upper()
        connection.execute(
            """
            INSERT INTO pending_appointment_actions
            (action_id, thread_ref, operation, payload_json, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (action_id, thread_ref, operation, encoded, now, now + ttl),
        )
        row = connection.execute(
            "SELECT * FROM pending_appointment_actions WHERE action_id = ?", (action_id,)
        ).fetchone()
        return dict(row), True


def _deserialize(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json"))
    return result


def get_pending_action(thread_ref: str) -> dict[str, Any] | None:
    """Return an unexpired pending action for this exact patient/session thread."""
    now = _now()
    with _database() as connection:
        connection.execute(
            "UPDATE pending_appointment_actions SET status='expired', outcome='Confirmation expired' "
            "WHERE thread_ref = ? AND status='pending' AND expires_at <= ?",
            (thread_ref, now),
        )
        row = connection.execute(
            """
            SELECT * FROM pending_appointment_actions
            WHERE thread_ref = ? AND status = 'pending' AND expires_at > ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (thread_ref, now),
        ).fetchone()
    return _deserialize(row) if row else None


def claim_pending_action(thread_ref: str) -> dict[str, Any] | None:
    """Atomically claim the pending action so repeated requests cannot execute it twice."""
    now = _now()
    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE pending_appointment_actions SET status='expired', outcome='Confirmation expired' "
            "WHERE thread_ref = ? AND status='pending' AND expires_at <= ?",
            (thread_ref, now),
        )
        row = connection.execute(
            """
            SELECT * FROM pending_appointment_actions
            WHERE thread_ref = ? AND status = 'pending' AND expires_at > ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (thread_ref, now),
        ).fetchone()
        if row is None:
            return None
        cursor = connection.execute(
            """
            UPDATE pending_appointment_actions SET status='processing'
            WHERE action_id = ? AND status = 'pending' AND expires_at > ?
            """,
            (row["action_id"], now),
        )
        if cursor.rowcount != 1:
            return None
        return _deserialize(row)


def finish_pending_action(action_id: str, status: str, outcome: str) -> bool:
    if status not in TERMINAL_STATUSES:
        raise ValueError("Invalid terminal pending-action status")
    with _database() as connection:
        cursor = connection.execute(
            """
            UPDATE pending_appointment_actions SET status = ?, outcome = ?
            WHERE action_id = ? AND status = 'processing'
            """,
            (status, str(outcome)[:500], action_id),
        )
        return cursor.rowcount == 1


def cancel_pending_action(thread_ref: str, outcome: str = "Patient declined confirmation") -> bool:
    with _database() as connection:
        cursor = connection.execute(
            """
            UPDATE pending_appointment_actions SET status='cancelled', outcome=?
            WHERE thread_ref=? AND status='pending'
            """,
            (outcome[:500], thread_ref),
        )
        return cursor.rowcount == 1


def format_pending_action(action: dict[str, Any]) -> str:
    payload = _deserialize(action) if "payload_json" in action else action
    details = payload["payload"]
    operation = payload["operation"]
    doctor = details["doctor_name"]
    if operation == "book":
        summary = f"book an appointment with {doctor} at {details['desired_date']}"
    elif operation == "cancel":
        summary = f"cancel the appointment with {doctor} at {details['date']}"
    else:
        summary = (
            f"reschedule the appointment with {doctor} from {details['old_date']} "
            f"to {details['new_date']}"
        )
    return f"{operation.upper()}: {summary}"


def build_prepare_tool(thread_ref: str):
    """Build the only appointment-mutation-related tool the LLM is allowed to call."""
    @tool
    def prepare_appointment_change(
        operation: Literal["book", "cancel", "reschedule"],
        doctor_name: Literal[
            "kevin anderson", "robert martinez", "susan davis", "daniel miller",
            "sarah wilson", "michael green", "lisa brown", "jane smith",
            "emily johnson", "john doe",
        ],
        appointment_date: str | None = None,
        old_appointment_date: str | None = None,
        new_appointment_date: str | None = None,
    ) -> str:
        """Prepare a booking, cancellation, or reschedule for patient confirmation. This never mutates the appointment schedule."""
        try:
            if operation == "book":
                payload = {"doctor_name": doctor_name, "desired_date": appointment_date}
            elif operation == "cancel":
                payload = {"doctor_name": doctor_name, "date": appointment_date}
            else:
                payload = {
                    "doctor_name": doctor_name,
                    "old_date": old_appointment_date,
                    "new_date": new_appointment_date,
                }
            action, created = create_pending_action(thread_ref, operation, payload)
        except (ValueError, TypeError) as exc:
            return f"No action was prepared. Ask for the missing or correctly formatted details: {exc}."

        label = format_pending_action(action)
        if not created:
            return (
                f"An appointment action is already awaiting confirmation for this conversation: {label}. "
                "Do not replace it or claim any change was made."
            )
        return (
            f"Prepared pending action {action['action_id']}: {label}. NO APPOINTMENT CHANGE HAS BEEN MADE. "
            "Tell the patient the exact action above and ask for a separate, explicit confirmation. "
            "The API executes only this stored action if the next message is exactly YES (or نعم/أيوه). "
            "The exact message NO (or لا) declines it. Any other message does not cause a mutation."
        )

    return prepare_appointment_change


def classify_confirmation(message: str) -> str:
    """Classify only exact short phrases; mixed/ambiguous sentences never approve a mutation."""
    normalized = unicodedata.normalize("NFKC", message or "").casefold().strip()
    normalized = normalized.replace("ـ", "")
    normalized = re.sub(r"[.!?؟،,;:]+", " ", normalized)
    normalized = " ".join(normalized.split())
    # Keep this deliberately narrow: the user must send a standalone confirmation.
    affirmative = {"yes", "نعم", "ايوه", "أيوه", "أيوة"}
    negative = {"no", "لا"}
    if normalized in affirmative:
        return "affirmative"
    if normalized in negative:
        return "negative"
    return "ambiguous"
