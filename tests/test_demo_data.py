from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from data_models.models import DateTimeModel, IdentificationNumberModel
from knowledge_base import load_faq
from toolkit.toolkits import _load_appointments, cancel_appointment, set_appointment

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "deployment" / "demo_data"
DEMO_FAQ = DEMO_DIR / "clinic_faq.json"
DEMO_APPOINTMENTS = DEMO_DIR / "doctor_availability.csv"

ALLOWED_DOCTORS = {
    "kevin anderson", "robert martinez", "susan davis", "daniel miller",
    "sarah wilson", "michael green", "lisa brown", "jane smith",
    "emily johnson", "john doe",
}
ALLOWED_SPECIALTIES = {
    "general_dentist", "cosmetic_dentist", "prosthodontist",
    "pediatric_dentist", "emergency_dentist", "oral_surgeon", "orthodontist",
}


def test_demo_faq_is_loadable_and_every_answer_is_marked_fake():
    entries = load_faq(DEMO_FAQ)

    assert len(entries) == 6
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert all(answer["answer"].startswith("DEMO ONLY") for answer in entries)
    assert all("NOT clinic-approved" in answer["source"]["title"] for answer in entries)
    assert all("not reviewed by a clinic" in answer["source"]["owner"] for answer in entries)


def test_demo_appointment_schedule_matches_tool_schema_and_has_valid_states():
    data = _load_appointments(DEMO_APPOINTMENTS)

    assert len(data) == 18
    assert set(data["doctor_name"].dropna().str.lower()).issubset(ALLOWED_DOCTORS)
    assert set(data["specialization"].dropna()).issubset(ALLOWED_SPECIALTIES)
    assert not data.duplicated(["date_slot", "doctor_name"]).any()
    assert data["is_available"].map(lambda value: isinstance(value, bool)).all()
    assert not (data["is_available"] & data["patient_to_attend"].notna()).any()
    assert not ((~data["is_available"]) & data["patient_to_attend"].isna()).any()
    assert data["patient_to_attend"].dropna().astype(int).between(9_000_000, 9_999_999).all()


def test_demo_booking_and_cancellation_mutate_only_a_temporary_copy(tmp_path, monkeypatch):
    original_bytes = DEMO_APPOINTMENTS.read_bytes()
    isolated_csv = tmp_path / "demo-copy.csv"
    shutil.copyfile(DEMO_APPOINTMENTS, isolated_csv)
    monkeypatch.setenv("APPOINTMENT_CSV_PATH", str(isolated_csv))

    booking = set_appointment.invoke({
        "desired_date": DateTimeModel(date="12-10-2026 09:00"),
        "id_number": IdentificationNumberModel(id=9123456),
        "doctor_name": "john doe",
    })
    assert booking == "Successfully done"
    booked = pd.read_csv(isolated_csv).query("date_slot == '12-10-2026 09:00'").iloc[0]
    assert not bool(booked["is_available"])
    assert int(booked["patient_to_attend"]) == 9123456

    cancellation = cancel_appointment.invoke({
        "date": DateTimeModel(date="12-10-2026 09:00"),
        "id_number": IdentificationNumberModel(id=9123456),
        "doctor_name": "john doe",
    })
    assert cancellation == "Successfully cancelled"
    cancelled = pd.read_csv(isolated_csv).query("date_slot == '12-10-2026 09:00'").iloc[0]
    assert bool(cancelled["is_available"])
    assert pd.isna(cancelled["patient_to_attend"])

    assert DEMO_APPOINTMENTS.read_bytes() == original_bytes
