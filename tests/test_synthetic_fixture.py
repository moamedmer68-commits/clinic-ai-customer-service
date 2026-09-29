import csv
from pathlib import Path


def test_synthetic_appointment_fixture_has_expected_schema_and_only_test_records():
    fixture = Path(__file__).parent / "fixtures" / "synthetic_appointments.csv"
    with fixture.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 10
    assert set(rows[0]) == {
        "date_slot", "specialization", "doctor_name", "is_available", "patient_to_attend"
    }
    assert all(row["doctor_name"].startswith("dr_test_") for row in rows)
    assert all(row["patient_to_attend"] in {"", "990001", "990002", "990003", "990004"} for row in rows)
