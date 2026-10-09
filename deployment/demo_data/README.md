# Synthetic demo data — NOT real clinic data

This directory contains intentionally fabricated content for local software demonstrations and automated testing only.

- `clinic_faq.json`: six clearly labelled sample FAQ answers. None is clinic-approved.
- `doctor_availability.csv`: 18 synthetic appointment slots with generic demo doctor names and test-only patient IDs (`9100001`–`9100005`). These are not real people, bookings, or availability.
- Dates and times are frozen sample values and will not track a real clinic's schedule.
- All sample FAQ answers begin with an explicit `DEMO ONLY` warning.

## Prepare a local Docker Compose demo

From the repository root in PowerShell:

```powershell
.\deployment\prepare_demo_data.ps1
```

The script requires the confirmation phrase `DEMO-ONLY` and refuses to run if `runtime-data\` already exists. It never overwrites existing local runtime data. Review its output before continuing.

Then provide an OpenAI API key and a fresh, high-entropy API access token in your ignored local `.env` file, without committing either secret. A token can be generated with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Run the demo:

```powershell
docker compose config --quiet
docker compose up --build
```

Open `http://127.0.0.1:8501`. The API remains bound to `127.0.0.1:8003`. Use a disposable test ID such as `9123456` in the UI. The booked rows in the CSV use synthetic IDs only.

## Safety and reset

Never point this data at real patient workflows or describe the displayed slots as genuine availability. The API writes bookings to the configured CSV, so a demo booking will change the local copy under ignored `runtime-data\`. To reset the demo, first stop Compose and manually verify that `runtime-data\` contains only these disposable fake files and demo-created local databases; only then remove that directory and re-run the setup script. Do not delete it if it contains any data you need.

This sample is deliberately not copied automatically into `data/clinic_faq.json` or `data/doctor_availability.csv`. The historical repository CSV remains untouched.
