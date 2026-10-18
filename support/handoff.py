from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


HandoffStatus = Literal["pending", "acknowledged", "resolved", "cancelled"]
_VALID_HANDOFF_STATUSES = {"pending", "acknowledged", "resolved", "cancelled"}

_CASE_ID_RE = re.compile(r"[^A-Z0-9_-]+")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_LONG_NUMBER_RE = re.compile(r"\b\d{7,16}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\d{3,4}[\s.-]?){2,3}\d{3,4}(?!\d)")


class HandoffError(RuntimeError):
    """Raised when a local human-handoff case cannot be created or updated."""


def default_handoff_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "human_handoffs.sqlite3"


def _db_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.getenv("HANDOFF_DB_PATH")
    return Path(configured) if configured else default_handoff_db_path()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _redact_sensitive(text: str) -> str:
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _LONG_NUMBER_RE.sub("[REDACTED_ID]", text)
    return _PHONE_RE.sub("[REDACTED_PHONE]", text)


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        role = message.get("role") or message.get("type") or "message"
        return str(role)
    message_type = getattr(message, "type", None)
    if message_type:
        return str(message_type)
    return "message"


def _message_content(message: Any) -> str:
    content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
    if not isinstance(content, str):
        return str(content)
    return content


def build_handoff_summary(messages: list[Any], max_messages: int = 6, max_chars_per_message: int = 600) -> str:
    """Build a bounded, privacy-minimized summary from the latest conversation turns."""
    lines: list[str] = []
    for message in messages[-max_messages:]:
        role = _message_role(message).lower()
        if role in {"human", "user"}:
            label = "Patient"
        elif role == "ai":
            label = "Assistant"
        else:
            label = role.title()
        content = _redact_sensitive(_message_content(message).strip())
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = content[: max_chars_per_message - 3].rstrip() + "..."
        lines.append(f"{label}: {content}")
    return "\n".join(lines) or "No conversation context was available."


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS handoff_cases (
            case_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL,
            trigger TEXT NOT NULL,
            summary TEXT NOT NULL,
            thread_ref TEXT
        )
        """
    )
    connection.commit()


def _new_case_id() -> str:
    suffix = hashlib.sha256(uuid4().bytes).hexdigest()[:10].upper()
    return _CASE_ID_RE.sub("", f"HND-{datetime.now(timezone.utc):%Y%m%d}-{suffix}")


def create_handoff_case(
    messages: list[Any],
    trigger: str,
    *,
    thread_ref: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, str]:
    """Create a pending local handoff case without claiming human response."""
    path = _db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    case_id = _new_case_id()
    now = _utc_now()
    summary = build_handoff_summary(messages)
    safe_thread_ref = _redact_sensitive(thread_ref) if thread_ref else None
    try:
        with sqlite3.connect(str(path), timeout=10) as connection:
            _ensure_schema(connection)
            connection.execute(
                """
                INSERT INTO handoff_cases
                    (case_id, created_at, updated_at, status, trigger, summary, thread_ref)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                (case_id, now, now, trigger, summary, safe_thread_ref),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise HandoffError("Unable to persist the local handoff case") from exc
    return {
        "case_id": case_id,
        "status": "pending",
        "trigger": trigger,
        "created_at": now,
        "summary": summary,
    }


def get_handoff_case(case_id: str, *, db_path: str | Path | None = None) -> dict[str, str] | None:
    path = _db_path(db_path)
    if not path.exists():
        return None
    with sqlite3.connect(str(path), timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT case_id, created_at, updated_at, status, trigger, summary, thread_ref FROM handoff_cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
    return dict(row) if row else None


def update_handoff_status(
    case_id: str,
    status: HandoffStatus,
    *,
    db_path: str | Path | None = None,
) -> bool:
    if status not in _VALID_HANDOFF_STATUSES:
        raise ValueError(f"Unsupported handoff status: {status}")
    path = _db_path(db_path)
    if not path.exists():
        return False
    now = _utc_now()
    with sqlite3.connect(str(path), timeout=10) as connection:
        _ensure_schema(connection)
        cursor = connection.execute(
            "UPDATE handoff_cases SET status = ?, updated_at = ? WHERE case_id = ?",
            (status, now, case_id),
        )
        connection.commit()
    return cursor.rowcount == 1


def list_pending_handoffs(*, db_path: str | Path | None = None, limit: int = 50) -> list[dict[str, str]]:
    path = _db_path(db_path)
    if not path.exists():
        return []
    safe_limit = max(1, min(int(limit), 200))
    with sqlite3.connect(str(path), timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT case_id, created_at, updated_at, status, trigger, summary, thread_ref
            FROM handoff_cases
            WHERE status IN ('pending', 'acknowledged')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def format_handoff_response(case: dict[str, str]) -> str:
    return (
        "I’ve escalated this request to the clinic support queue. "
        f"Your case ID is {case['case_id']}. "
        "The current status is pending human review. "
        "I have not received a human response yet."
    )


def format_handoff_failure() -> str:
    return (
        "I’m unable to create the human-support case right now. "
        "No human has been contacted through the system. Please contact the clinic directly."
    )


def detect_escalation_trigger(query: str) -> str | None:
    """Detect high-confidence user-requested or sensitive escalation signals."""
    normalized = re.sub(r"\s+", " ", query.casefold()).strip()
    if re.search(r"\b(speak|talk|connect|transfer)\b.{0,40}\b(human|person|representative|operator|manager)\b", normalized):
        return "human_requested"
    if re.search(r"\b(human|person|representative|operator|manager)\b.{0,40}\b(agent|support|help|please)\b", normalized):
        return "human_requested"
    if re.search(r"\b(file|make|submit|register|raise)\b.{0,30}\b(a )?(complaint|complain)\b", normalized) or "formal complaint" in normalized:
        return "complaint_requested"
    if re.search(r"\b(speak|talk|connect)\b.{0,40}\b(manager|supervisor)\b", normalized):
        return "complaint_requested"
    if re.search(r"\b(urgent|severe|heavy)\b.{0,30}\b(bleeding|pain|swelling|swollen|infection)\b", normalized):
        return "sensitive_medical_request"
    return None


__all__ = [
    "HandoffError",
    "build_handoff_summary",
    "create_handoff_case",
    "default_handoff_db_path",
    "detect_escalation_trigger",
    "format_handoff_failure",
    "format_handoff_response",
    "get_handoff_case",
    "list_pending_handoffs",
    "update_handoff_status",
]
