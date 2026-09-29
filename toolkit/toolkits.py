import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pandas as pd
from langchain_core.tools import tool

from data_models.models import DateModel, DateTimeModel, IdentificationNumberModel


REQUIRED_COLUMNS = {"date_slot", "specialization", "doctor_name", "is_available", "patient_to_attend"}
DATA_ERROR = "Appointment data is unavailable. Please try again later."


class AppointmentDataError(Exception):
    """Raised when the CSV cannot safely be used as an appointment store."""


def get_csv_path() -> Path:
    """Return the single authoritative CSV path for doctor availability."""
    override_path = os.getenv("APPOINTMENT_CSV_PATH")
    if override_path:
        return Path(override_path)
    base_dir = Path(__file__).resolve().parent.parent
    primary_path = base_dir / "data" / "doctor_availability.csv"
    return primary_path if primary_path.exists() else base_dir / "doctor_availability.csv"


def parse_and_format_datetime(dt_str: str) -> str:
    """Parse a real DD-MM-YYYY HH:MM timestamp into its canonical representation."""
    return datetime.strptime(dt_str.strip(), "%d-%m-%Y %H:%M").strftime("%d-%m-%Y %H:%M")


@contextmanager
def _csv_lock(csv_path: Path, timeout_seconds: float = 5.0):
    """Use an exclusive lock file so CSV read-modify-write mutations cannot race."""
    lock_path = csv_path.with_name(f"{csv_path.name}.lock")
    deadline = time.monotonic() + timeout_seconds
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise AppointmentDataError("Timed out waiting for appointment data")
            time.sleep(0.02)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _load_appointments(csv_path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path, dtype={"date_slot": "string", "doctor_name": "string", "specialization": "string"})
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise AppointmentDataError("CSV could not be read") from exc
    if not REQUIRED_COLUMNS.issubset(df.columns):
        raise AppointmentDataError("CSV is missing required columns")
    try:
        df["date_slot"] = df["date_slot"].map(parse_and_format_datetime)
    except (TypeError, ValueError) as exc:
        raise AppointmentDataError("CSV contains an invalid appointment time") from exc
    if not df["is_available"].map(lambda value: isinstance(value, bool)).all():
        raise AppointmentDataError("CSV contains an invalid availability value")
    if df.duplicated(["date_slot", "doctor_name"]).any():
        raise AppointmentDataError("CSV contains duplicate appointment slots")
    available_without_empty_patient = df["is_available"] & df["patient_to_attend"].notna()
    unavailable_without_patient = ~df["is_available"] & df["patient_to_attend"].isna()
    if available_without_empty_patient.any() or unavailable_without_patient.any():
        raise AppointmentDataError("CSV violates appointment state invariants")
    return df


def _write_appointments(df: pd.DataFrame, csv_path: Path) -> None:
    """Atomically replace the CSV only after the complete new state has been written."""
    temporary_path = csv_path.with_name(f".{csv_path.name}.{uuid4().hex}.tmp")
    try:
        df.to_csv(temporary_path, index=False)
        os.replace(temporary_path, csv_path)
    except OSError as exc:
        raise AppointmentDataError("CSV could not be written") from exc
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _patient_matches(series: pd.Series, id_number: int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").eq(id_number)


def _availability_message(df: pd.DataFrame, desired_date: str, filter_mask: pd.Series, grouped: bool = False) -> str:
    rows = df[(df["date_slot"].str.startswith(f"{desired_date} ")) & filter_mask & df["is_available"]].copy()
    if rows.empty:
        return "No availability in the entire day"
    rows["date_slot_time"] = rows["date_slot"].str.split().str[-1]
    if not grouped:
        return f"This availability for {desired_date}\nAvailable slots: " + ", ".join(rows["date_slot_time"])
    output = f"This availability for {desired_date}\n"
    for (_, doctor_name), slots in rows.groupby(["specialization", "doctor_name"], sort=False):
        formatted_slots = []
        for value in slots["date_slot_time"]:
            formatted_slots.append(datetime.strptime(value, "%H:%M").strftime("%I:%M %p").lstrip("0"))
        output += f"{doctor_name}. Available slots: \n" + ", \n".join(formatted_slots) + "\n"
    return output


@tool
def check_availability_by_doctor(desired_date: DateModel, doctor_name: Literal['kevin anderson', 'robert martinez', 'susan davis', 'daniel miller', 'sarah wilson', 'michael green', 'lisa brown', 'jane smith', 'emily johnson', 'john doe']):
    """Check available slots for a doctor on the requested date."""
    try:
        df = _load_appointments(get_csv_path())
        return _availability_message(df, desired_date.date, df["doctor_name"].eq(doctor_name))
    except AppointmentDataError:
        return DATA_ERROR


@tool
def check_availability_by_specialization(desired_date: DateModel, specialization: Literal["general_dentist", "cosmetic_dentist", "prosthodontist", "pediatric_dentist", "emergency_dentist", "oral_surgeon", "orthodontist"]):
    """Check available slots for a specialization on the requested date."""
    try:
        df = _load_appointments(get_csv_path())
        return _availability_message(df, desired_date.date, df["specialization"].eq(specialization), grouped=True)
    except AppointmentDataError:
        return DATA_ERROR


@tool
def set_appointment(desired_date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal['kevin anderson', 'robert martinez', 'susan davis', 'daniel miller', 'sarah wilson', 'michael green', 'lisa brown', 'jane smith', 'emily johnson', 'john doe']):
    """Book one available appointment, without allowing double booking."""
    try:
        formatted_date = parse_and_format_datetime(desired_date.date)
        csv_path = get_csv_path()
        with _csv_lock(csv_path):
            df = _load_appointments(csv_path)
            mask = df["date_slot"].eq(formatted_date) & df["doctor_name"].eq(doctor_name)
            if mask.sum() != 1 or not bool(df.loc[mask, "is_available"].iloc[0]):
                return "No available appointments for that particular case"
            df.loc[mask, ["is_available", "patient_to_attend"]] = [False, id_number.id]
            _write_appointments(df, csv_path)
        return "Successfully done"
    except (AppointmentDataError, OSError):
        return DATA_ERROR
    except ValueError:
        return "No available appointments for that particular case"


@tool
def cancel_appointment(date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal['kevin anderson', 'robert martinez', 'susan davis', 'daniel miller', 'sarah wilson', 'michael green', 'lisa brown', 'jane smith', 'emily johnson', 'john doe']):
    """Cancel only the matching patient's existing appointment."""
    try:
        formatted_date = parse_and_format_datetime(date.date)
        csv_path = get_csv_path()
        with _csv_lock(csv_path):
            df = _load_appointments(csv_path)
            mask = (df["date_slot"].eq(formatted_date) & df["doctor_name"].eq(doctor_name)
                    & ~df["is_available"] & _patient_matches(df["patient_to_attend"], id_number.id))
            if mask.sum() != 1:
                return "No appointment found matching the provided details."
            df.loc[mask, ["is_available", "patient_to_attend"]] = [True, None]
            _write_appointments(df, csv_path)
        return "Successfully cancelled"
    except (AppointmentDataError, OSError):
        return DATA_ERROR
    except ValueError:
        return "No appointment found matching the provided details."


@tool
def reschedule_appointment(old_date: DateTimeModel, new_date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal['kevin anderson', 'robert martinez', 'susan davis', 'daniel miller', 'sarah wilson', 'michael green', 'lisa brown', 'jane smith', 'emily johnson', 'john doe']):
    """Atomically move a patient's appointment, retaining the old booking on failure."""
    try:
        old_slot = parse_and_format_datetime(old_date.date)
        new_slot = parse_and_format_datetime(new_date.date)
        csv_path = get_csv_path()
        with _csv_lock(csv_path):
            df = _load_appointments(csv_path)
            old_mask = (df["date_slot"].eq(old_slot) & df["doctor_name"].eq(doctor_name)
                        & ~df["is_available"] & _patient_matches(df["patient_to_attend"], id_number.id))
            new_mask = df["date_slot"].eq(new_slot) & df["doctor_name"].eq(doctor_name)
            if old_mask.sum() != 1:
                return "No appointment found matching the provided details."
            if new_mask.sum() != 1 or not bool(df.loc[new_mask, "is_available"].iloc[0]):
                return "Not available slots in the desired period"
            df.loc[old_mask, ["is_available", "patient_to_attend"]] = [True, None]
            df.loc[new_mask, ["is_available", "patient_to_attend"]] = [False, id_number.id]
            _write_appointments(df, csv_path)
        return "Successfully rescheduled for the desired time"
    except (AppointmentDataError, OSError):
        return DATA_ERROR
    except ValueError:
        return "Not available slots in the desired period"
