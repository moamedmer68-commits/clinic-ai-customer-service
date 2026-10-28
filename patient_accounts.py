from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


class Base(DeclarativeBase):
    pass


class PatientAccount(Base):
    __tablename__ = "patient_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_salt: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    patient_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PatientSession(Base):
    __tablename__ = "patient_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("patient_accounts.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def make_engine(database_url: str):
    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            kwargs["poolclass"] = NullPool
    return create_engine(database_url, **kwargs)


def initialize_database(engine) -> None:
    Base.metadata.create_all(engine)


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    _, actual = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(actual, expected_hash)


def create_pending_account(db: Session, *, full_name: str, email: str, phone: str | None, password: str) -> PatientAccount:
    normalized_email = email.strip().lower()
    if db.scalar(select(PatientAccount).where(PatientAccount.email == normalized_email)):
        raise ValueError("An account with this email already exists.")
    salt, digest = _hash_password(password)
    account = PatientAccount(
        full_name=full_name.strip(),
        email=normalized_email,
        phone=phone.strip() if phone else None,
        password_salt=salt,
        password_hash=digest,
        status="pending_review",
    )
    db.add(account)
    db.commit()
    return account


def approve_account(db: Session, account_id: int) -> PatientAccount | None:
    account = db.get(PatientAccount, account_id)
    if account is None:
        return None
    if account.status == "approved" and account.patient_id:
        return account
    if account.status != "pending_review":
        raise ValueError("Only accounts awaiting review can be approved.")
    # A random, non-sequential identifier avoids exposing account counts.
    account.patient_id = str(secrets.randbelow(90_000_000) + 10_000_000)
    while db.scalar(select(PatientAccount.id).where(PatientAccount.patient_id == account.patient_id, PatientAccount.id != account.id)) is not None:
        account.patient_id = str(secrets.randbelow(90_000_000) + 10_000_000)
    account.status = "approved"
    account.approved_at = _utcnow()
    db.commit()
    return account


def authenticate_and_create_session(db: Session, *, email: str, password: str) -> tuple[PatientAccount | None, str | None]:
    account = db.scalar(select(PatientAccount).where(PatientAccount.email == email.strip().lower()))
    # Keep the public failure generic to avoid revealing whether an email exists.
    if account is None or not verify_password(password, account.password_salt, account.password_hash):
        return None, None
    if account.status != "approved" or not account.patient_id:
        return account, None
    raw_token = secrets.token_urlsafe(32)
    db.add(PatientSession(
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        account_id=account.id,
        expires_at=_utcnow() + timedelta(hours=12),
    ))
    db.commit()
    return account, raw_token


def account_for_token(db: Session, raw_token: str) -> PatientAccount | None:
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    session_row = db.scalar(select(PatientSession).where(PatientSession.token_hash == token_hash))
    if session_row is None or session_row.revoked_at is not None:
        return None
    expiry = session_row.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= _utcnow():
        return None
    account = db.get(PatientAccount, session_row.account_id)
    if account is None or account.status != "approved" or not account.patient_id:
        return None
    return account


def revoke_token(db: Session, raw_token: str) -> bool:
    if not raw_token:
        return False
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    session_row = db.scalar(select(PatientSession).where(PatientSession.token_hash == token_hash))
    if session_row is None or session_row.revoked_at is not None:
        return False
    session_row.revoked_at = _utcnow()
    db.commit()
    return True


def deactivate_account(db: Session, account_id: int) -> PatientAccount | None:
    """Deactivate an account and revoke every session in one database transaction."""
    account = db.get(PatientAccount, account_id)
    if account is None:
        return None
    now = _utcnow()
    account.status = "deactivated"
    sessions = db.scalars(
        select(PatientSession).where(
            PatientSession.account_id == account_id,
            PatientSession.revoked_at.is_(None),
        )
    ).all()
    for session_row in sessions:
        session_row.revoked_at = now
    db.commit()
    return account
