import os
from pathlib import Path
from datetime import datetime
from typing import Literal
import pandas as pd
from langchain_core.tools import tool
from data_models.models import DateModel, DateTimeModel, IdentificationNumberModel


def get_csv_path() -> Path:
    """Returns the single authoritative CSV path for doctor availability."""
    override_path = os.getenv("APPOINTMENT_CSV_PATH")
    if override_path:
        return Path(override_path)
    base_dir = Path(__file__).resolve().parent.parent
    primary_path = base_dir / "data" / "doctor_availability.csv"
    if primary_path.exists():
        return primary_path
    return base_dir / "doctor_availability.csv"


def parse_and_format_datetime(dt_str: str) -> str:
    """
    Parses a datetime string in DD-MM-YYYY HH:MM format and standardizes it to %d-%m-%Y %H:%M.
    Platform-independent and ensures exact timestamp matching.
    """
    dt = datetime.strptime(dt_str.strip(), "%d-%m-%Y %H:%M")
    return dt.strftime("%d-%m-%Y %H:%M")


@tool
def check_availability_by_doctor(desired_date: DateModel, doctor_name: Literal['kevin anderson','robert martinez','susan davis','daniel miller','sarah wilson','michael green','lisa brown','jane smith','emily johnson','john doe']):
    """
    Checking the database if we have availability for the specific doctor.
    The parameters should be mentioned by the user in the query
    """
    df = pd.read_csv(get_csv_path())

    df['date_slot_time'] = df['date_slot'].apply(lambda val: str(val).split(' ')[-1])
    df['date_slot_date'] = df['date_slot'].apply(lambda val: str(val).split(' ')[0])

    rows = list(df[(df['date_slot_date'] == desired_date.date) & (df['doctor_name'] == doctor_name) & (df['is_available'] == True)]['date_slot_time'])

    if len(rows) == 0:
        output = "No availability in the entire day"
    else:
        output = f'This availability for {desired_date.date}\n'
        output += "Available slots: " + ', '.join(rows)

    return output


@tool
def check_availability_by_specialization(desired_date: DateModel, specialization: Literal["general_dentist", "cosmetic_dentist", "prosthodontist", "pediatric_dentist","emergency_dentist","oral_surgeon","orthodontist"]):
    """
    Checking the database if we have availability for the specific specialization.
    The parameters should be mentioned by the user in the query
    """
    df = pd.read_csv(get_csv_path())
    df['date_slot_time'] = df['date_slot'].apply(lambda val: str(val).split(' ')[-1])
    df['date_slot_date'] = df['date_slot'].apply(lambda val: str(val).split(' ')[0])

    rows = df[(df['date_slot_date'] == desired_date.date) & (df['specialization'] == specialization) & (df['is_available'] == True)].groupby(['specialization', 'doctor_name'])['date_slot_time'].apply(list).reset_index(name='available_slots')

    if len(rows) == 0:
        output = "No availability in the entire day"
    else:
        def convert_to_am_pm(time_str):
            time_str = str(time_str)
            hours, minutes = map(int, time_str.split(":"))
            period = "AM" if hours < 12 else "PM"
            hours = hours % 12 or 12
            return f"{hours}:{minutes:02d} {period}"

        output = f'This availability for {desired_date.date}\n'
        for row in rows.values:
            output += row[1] + ". Available slots: \n" + ', \n'.join([convert_to_am_pm(value) for value in row[2]]) + '\n'

    return output


@tool
def set_appointment(desired_date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal['kevin anderson','robert martinez','susan davis','daniel miller','sarah wilson','michael green','lisa brown','jane smith','emily johnson','john doe']):
    """
    Set appointment or slot with the doctor.
    The parameters MUST be mentioned by the user in the query.
    """
    csv_path = get_csv_path()
    df = pd.read_csv(csv_path)

    try:
        formatted_date = parse_and_format_datetime(desired_date.date)
    except Exception:
        return "No available appointments for that particular case"

    mask = (df['date_slot'] == formatted_date) & (df['doctor_name'] == doctor_name)
    matching_rows = df[mask]

    if len(matching_rows) == 0:
        return "No available appointments for that particular case"

    available_rows = matching_rows[matching_rows['is_available'] == True]
    if len(available_rows) == 0:
        return "No available appointments for that particular case"

    df.loc[mask & (df['is_available'] == True), ['is_available', 'patient_to_attend']] = [False, id_number.id]
    df.to_csv(csv_path, index=False)

    return "Successfully done"


@tool
def cancel_appointment(date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal['kevin anderson','robert martinez','susan davis','daniel miller','sarah wilson','michael green','lisa brown','jane smith','emily johnson','john doe']):
    """
    Canceling an appointment.
    The parameters MUST be mentioned by the user in the query.
    """
    csv_path = get_csv_path()
    df = pd.read_csv(csv_path)

    try:
        formatted_date = parse_and_format_datetime(date.date)
    except Exception:
        return "No appointment found matching the provided details."

    patient_matches = pd.to_numeric(df['patient_to_attend'], errors='coerce') == id_number.id
    mask = (df['date_slot'] == formatted_date) & (df['doctor_name'] == doctor_name) & patient_matches & (df['is_available'] == False)
    case_to_remove = df[mask]

    if len(case_to_remove) == 0:
        return "No appointment found matching the provided details."
    else:
        df.loc[mask, ['is_available', 'patient_to_attend']] = [True, None]
        df.to_csv(csv_path, index=False)

        return "Successfully cancelled"


@tool
def reschedule_appointment(old_date: DateTimeModel, new_date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal['kevin anderson','robert martinez','susan davis','daniel miller','sarah wilson','michael green','lisa brown','jane smith','emily johnson','john doe']):
    """
    Rescheduling an appointment.
    The parameters MUST be mentioned by the user in the query.
    """
    csv_path = get_csv_path()
    df = pd.read_csv(csv_path)

    try:
        new_date_formatted = parse_and_format_datetime(new_date.date)
    except Exception:
        return "Not available slots in the desired period"

    available_for_desired_date = df[(df['date_slot'] == new_date_formatted) & (df['is_available'] == True) & (df['doctor_name'] == doctor_name)]
    if len(available_for_desired_date) == 0:
        return "Not available slots in the desired period"
    else:
        cancel_result = cancel_appointment.invoke({'date': old_date, 'id_number': id_number, 'doctor_name': doctor_name})
        if "Successfully cancelled" not in str(cancel_result):
            return cancel_result
        set_result = set_appointment.invoke({'desired_date': new_date, 'id_number': id_number, 'doctor_name': doctor_name})
        if "Successfully done" not in str(set_result):
            return set_result
        return "Successfully rescheduled for the desired time"
