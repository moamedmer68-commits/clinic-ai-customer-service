from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Integer, String, create_engine, select, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


class SecurityBase(DeclarativeBase):
    pass


class LoginThrottle(SecurityBase):
    __tablename__ = "login_throttles"

    identifier_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SecurityAuditEvent(SecurityBase):
    __tablename__ = "security_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    target_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def make_security_engine(database_url: str):
    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            kwargs["poolclass"] = NullPool
    return create_engine(database_url, **kwargs)


def initialize_security_tables(engine) -> None:
    SecurityBase.metadata.create_all(engine)


def security_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier(email: str) -> str:
    # Store only a one-way identifier; never persist the submitted email in throttle records.
    normalized = email.strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def login_is_locked(db: Session, email: str) -> bool:
    row = db.get(LoginThrottle, _identifier(email))
    if row is None or row.locked_until is None:
        return False
    locked_until = row.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until <= _now():
        row.locked_until = None
        row.failures = 0
        row.window_started_at = _now()
        db.commit()
        return False
    return True


def record_login_failure(db: Session, email: str) -> None:
    now = _now()
    key = _identifier(email)
    row = db.get(LoginThrottle, key)
    if row is None:
        row = LoginThrottle(identifier_hash=key, failures=0, window_started_at=now)
        db.add(row)
        db.flush()
    window_start = row.window_started_at
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if now - window_start > timedelta(minutes=15):
        row.failures = 0
        row.window_started_at = now
        row.locked_until = None
    row.failures += 1
    if row.failures >= 5:
        row.locked_until = now + timedelta(minutes=15)
    db.commit()


def clear_login_failures(db: Session, email: str) -> None:
    db.execute(delete(LoginThrottle).where(LoginThrottle.identifier_hash == _identifier(email)))
    db.commit()


def write_audit_event(
    db: Session, *, event_type: str, request_id: str, target_account_id: int | None = None
) -> None:
    # Deliberately excludes email, phone, patient ID, passwords, tokens and request bodies.
    db.add(SecurityAuditEvent(
        event_type=event_type[:64],
        request_id=request_id[:64],
        target_account_id=target_account_id,
        created_at=_now(),
    ))
    db.commit()
