import os
import shutil
import tempfile
import unittest
from pathlib import Path
import pandas as pd

from data_models.models import DateModel, DateTimeModel, IdentificationNumberModel
from toolkit.toolkits import (
    check_availability_by_doctor,
    check_availability_by_specialization,
    set_appointment,
    cancel_appointment,
    reschedule_appointment,
    parse_and_format_datetime,
    get_csv_path,
)


class TestAppointmentTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.temp_csv = Path(cls.temp_dir) / "test_doctor_availability.csv"

        # Initial test CSV data
        initial_data = pd.DataFrame([
            {
                "date_slot": "08-08-2024 08:00",
                "specialization": "general_dentist",
                "doctor_name": "john doe",
                "is_available": True,
                "patient_to_attend": None,
            },
            {
                "date_slot": "08-08-2024 18:00",
                "specialization": "general_dentist",
                "doctor_name": "john doe",
                "is_available": True,
                "patient_to_attend": None,
            },
            {
                "date_slot": "08-08-2024 10:00",
                "specialization": "general_dentist",
                "doctor_name": "john doe",
                "is_available": False,
                "patient_to_attend": 1000042,
            },
            {
                "date_slot": "09-08-2024 09:00",
                "specialization": "orthodontist",
                "doctor_name": "jane smith",
                "is_available": True,
                "patient_to_attend": None,
            },
        ])
        initial_data.to_csv(cls.temp_csv, index=False)
        os.environ["APPOINTMENT_CSV_PATH"] = str(cls.temp_csv)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("APPOINTMENT_CSV_PATH", None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        # Reset temp CSV to known state before each test
        initial_data = pd.DataFrame([
            {
                "date_slot": "08-08-2024 08:00",
                "specialization": "general_dentist",
                "doctor_name": "john doe",
                "is_available": True,
                "patient_to_attend": None,
            },
            {
                "date_slot": "08-08-2024 18:00",
                "specialization": "general_dentist",
                "doctor_name": "john doe",
                "is_available": True,
                "patient_to_attend": None,
            },
            {
                "date_slot": "08-08-2024 10:00",
                "specialization": "general_dentist",
                "doctor_name": "john doe",
                "is_available": False,
                "patient_to_attend": 1000042,
            },
            {
                "date_slot": "09-08-2024 09:00",
                "specialization": "orthodontist",
                "doctor_name": "jane smith",
                "is_available": True,
                "patient_to_attend": None,
            },
        ])
        initial_data.to_csv(self.temp_csv, index=False)

    def test_1_book_existing_available_appointment(self):
        """TEST 1: An existing available appointment can be booked."""
        desired_date = DateTimeModel(date="08-08-2024 08:00")
        id_num = IdentificationNumberModel(id=1234567)
        res = set_appointment.invoke({
            "desired_date": desired_date,
            "id_number": id_num,
            "doctor_name": "john doe",
        })
        self.assertEqual(res, "Successfully done")

    def test_2_booking_updates_same_csv_as_availability_lookup(self):
        """TEST 2: The booking operation updates the SAME CSV that availability lookup reads."""
        desired_date = DateTimeModel(date="08-08-2024 08:00")
        id_num = IdentificationNumberModel(id=1234567)
        set_appointment.invoke({
            "desired_date": desired_date,
            "id_number": id_num,
            "doctor_name": "john doe",
        })

        # Read directly from get_csv_path() and via check_availability_by_doctor
        lookup_res = check_availability_by_doctor.invoke({
            "desired_date": DateModel(date="08-08-2024"),
            "doctor_name": "john doe",
        })
        self.assertNotIn("08:00", lookup_res)
        self.assertIn("18:00", lookup_res)

        df = pd.read_csv(get_csv_path())
        booked_row = df[df["date_slot"] == "08-08-2024 08:00"].iloc[0]
        self.assertFalse(booked_row["is_available"])
        self.assertEqual(int(booked_row["patient_to_attend"]), 1234567)

    def test_3_unavailable_appointment_cannot_be_booked(self):
        """TEST 3: An unavailable appointment cannot be booked."""
        desired_date = DateTimeModel(date="08-08-2024 10:00")
        id_num = IdentificationNumberModel(id=7654321)
        res = set_appointment.invoke({
            "desired_date": desired_date,
            "id_number": id_num,
            "doctor_name": "john doe",
        })
        self.assertEqual(res, "No available appointments for that particular case")

    def test_4_cancel_existing_appointment(self):
        """TEST 4: An existing appointment can be cancelled."""
        date = DateTimeModel(date="08-08-2024 10:00")
        id_num = IdentificationNumberModel(id=1000042)
        res = cancel_appointment.invoke({
            "date": date,
            "id_number": id_num,
            "doctor_name": "john doe",
        })
        self.assertEqual(res, "Successfully cancelled")

        df = pd.read_csv(get_csv_path())
        row = df[df["date_slot"] == "08-08-2024 10:00"].iloc[0]
        self.assertTrue(row["is_available"])

    def test_5_cancel_non_existent_appointment_fails(self):
        """TEST 5: Cancelling a non-existent appointment fails explicitly."""
        date = DateTimeModel(date="08-08-2024 10:00")
        id_num = IdentificationNumberModel(id=9999999)  # Wrong ID
        res = cancel_appointment.invoke({
            "date": date,
            "id_number": id_num,
            "doctor_name": "john doe",
        })
        self.assertEqual(res, "No appointment found matching the provided details.")

    def test_6_timestamp_parsing_format(self):
        """TEST 6: Timestamp parsing works with DD-MM-YYYY HH:MM."""
        res = parse_and_format_datetime("08-08-2024 08:00")
        self.assertEqual(res, "08-08-2024 08:00")

    def test_7_distinguishes_0800_from_1800(self):
        """TEST 7: 08:00 is correctly distinguished from 18:00."""
        res1 = parse_and_format_datetime("08-08-2024 08:00")
        res2 = parse_and_format_datetime("08-08-2024 18:00")
        self.assertNotEqual(res1, res2)
        self.assertEqual(res1, "08-08-2024 08:00")
        self.assertEqual(res2, "08-08-2024 18:00")

    def test_8_no_dependence_on_percent_hash_h(self):
        """TEST 8: The code does not depend on %#H."""
        # Ensure parse_and_format_datetime runs cleanly on standard string
        formatted = parse_and_format_datetime("05-08-2024 08:30")
        self.assertEqual(formatted, "05-08-2024 08:30")
        self.assertNotIn(".", formatted)

    def test_9_booking_then_cancellation_leaves_expected_state(self):
        """TEST 9: A booking followed by cancellation leaves the slot in expected final state."""
        dt = DateTimeModel(date="08-08-2024 08:00")
        id_num = IdentificationNumberModel(id=1234567)

        book_res = set_appointment.invoke({
            "desired_date": dt,
            "id_number": id_num,
            "doctor_name": "john doe",
        })
        self.assertEqual(book_res, "Successfully done")

        cancel_res = cancel_appointment.invoke({
            "date": dt,
            "id_number": id_num,
            "doctor_name": "john doe",
        })
        self.assertEqual(cancel_res, "Successfully cancelled")

        df = pd.read_csv(get_csv_path())
        row = df[df["date_slot"] == "08-08-2024 08:00"].iloc[0]
        self.assertTrue(row["is_available"])
        self.assertTrue(pd.isna(row["patient_to_attend"]))


if __name__ == "__main__":
    unittest.main()
