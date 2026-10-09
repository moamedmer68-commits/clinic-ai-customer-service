# Phase 10 — Production-readiness scaffold and release blockers

## Security configuration

The API requires a shared API_ACCESS_TOKEN for POST /execute by default. Tokens are compared in constant time and are never logged. Missing token configuration returns 503; invalid or missing credentials return 401. The explicit ALLOW_UNAUTHENTICATED_LOCAL_DEV=true switch exists only for local-only development and must remain false in deployment.

Generate a high-entropy token locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Place it in an untracked local .env file and share the same value with the API and Streamlit processes. Never commit .env or include the token in build arguments, logs, screenshots, or support tickets.

The /health/live endpoint reports process liveness. /health/ready and /health fail when model dependencies or required API security configuration are missing. Request IDs are restricted to a safe character set; all responses disable caching. OpenAI requests have bounded timeout and retry configuration.

The shared API token is a prototype service credential, not patient authentication or role-based authorization. Do not expose the service to the public Internet without HTTPS via a reverse proxy, proper end-user authentication/authorization, rate limiting, and an operator-approved privacy/security design.

## Reproducible runtime dependencies

- requirements-runtime.txt contains the small pinned dependency set for the supported API/UI runtime.
- requirements-test.txt layers the pinned test runner and HTTP test client on top.
- The historical requirements.txt remains the broader research environment with optional ML/CV and integration packages; CI and the container build use the runtime-specific files to avoid unrelated heavy native dependencies.
- `CLINIC_FAQ_PATH` now selects the FAQ source explicitly. Compose points it at `/app/runtime-data/clinic_faq.json`; the default local path remains `data/clinic_faq.json`.
- GitHub Actions checks dependency consistency, compiles modules, runs the full test suite, and builds the container image.

## Local container scaffold

Required host setup before running docker compose up --build:

1. For a disposable local demo only, run `deployment/prepare_demo_data.ps1`. It copies clearly labelled fake FAQ and appointment slots into ignored `runtime-data/`, requires explicit confirmation, and refuses to overwrite an existing runtime-data directory. Read `deployment/demo_data/README.md` first.
2. For a real-clinic deployment, do not use the demo kit. Create runtime-data/clinic_faq.json from facts explicitly approved by the clinic owner, or copy deployment/clinic_faq.example.json and replace all placeholders with reviewed facts.
3. Provision runtime-data/doctor_availability.csv only from an approved, current clinic source. Do not copy the historical repository CSV or synthetic demo CSV into a real-clinic deployment.
4. Set OPENAI_API_KEY and a strong API_ACCESS_TOKEN in the local .env file or deployment secret store; never commit secrets.
5. Ensure the mounted runtime-data/ is writable by the container user and adequately backed up.

Compose binds the API and UI ports to 127.0.0.1 by default. The image excludes .env, tests, notebooks, scratch files, and appointment CSV data. It runs as an unprivileged user. Runtime data is mounted outside the image so it can be provisioned and persisted independently.

Start with:

```powershell
docker compose up --build
```

Open the Streamlit UI at http://127.0.0.1:8501. The API is bound locally on port 8003. The Compose readiness check fails until the API can initialize its model and security configuration.

Local validation: `docker compose config --quiet` passed with placeholder environment variables. A local image build was attempted, but Docker Desktop's Linux engine pipe was unavailable. The image build must succeed on the hosted CI runner before relying on the container scaffold.

## Operational limitations — do not call this production-clinic ready

The repository is still a prototype. Remaining release blockers include:

- No clinic-approved FAQ corpus has been supplied; data/clinic_faq.json is empty in source.
- No authorized current appointment schedule has been supplied for deployment. The committed schedule is historical and must not be treated as live data.
- Appointment storage remains CSV with local-file locking; conversation memory and handoffs are SQLite. Multi-host/multi-worker production should move operational data to a transactional database and a shared managed checkpointer/queue.
- Human escalation creates a local queue case only. It does not notify or connect a live human operator.
- The shared API key is not patient authentication, and there is no per-role access control or patient self-service access model.
- Automated retention/deletion, encryption-at-rest policy, audit access controls, notification ownership, backups/restore rehearsal, rate limiting, load testing, security testing, cloud deployment, TLS/reverse proxy, and rollback rehearsal remain environment-specific production work.
- The browser layout and keyboard accessibility still require manual acceptance using docs/STREAMLIT_UI_ACCEPTANCE.md.

## Release checklist

- [ ] Clinic owner approves and dates all FAQ content.
- [ ] Data owner provisions an authorized current schedule without reusing the historical sample.
- [ ] Generate/store secrets outside source control and confirm API auth is enabled.
- [ ] Choose hosting, network exposure, TLS, identity/authentication, rate limiting, monitoring, retention, and incident ownership.
- [ ] Replace CSV/SQLite prototype stores where concurrency/multi-host operations require it.
- [ ] Run docker compose config, build, readiness check, API auth checks, full tests, failure tests, and manual UI acceptance.
- [ ] Rehearse backup/restore and release rollback with synthetic data.
- [ ] Obtain clinic security/privacy approval before real patient use.
