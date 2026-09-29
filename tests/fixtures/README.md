# Synthetic appointment fixture

`synthetic_appointments.csv` contains fabricated doctors, dates, and test-only patient IDs for local tests and demos.

- Never use this fixture as real clinic availability or patient data.
- It is intentionally stored under `tests/fixtures/`, not `data/`.
- Tests may point `APPOINTMENT_CSV_PATH` to this file only in an isolated temporary copy. Do not point a live app at it.
- The production `data/doctor_availability.csv` is not modified by this fixture.
