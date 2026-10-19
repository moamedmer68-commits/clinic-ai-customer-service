# Clinic AI Customer Service — Development Plan

**Document purpose:** The current agreed plan and working log for the next development cycle.
**Last updated:** 2026-10-15
**Repository:** moamedmer68-commits/clinic-ai-customer-service
**Working branch:** ci/fix-github-actions
**Current baseline:** ddd8b5854cb7084f26cf9ed83b11fed8f018e5f9
**Related source of truth:** ROADMAP.md remains the repository-wide record of implementation status and verification. This file records the newly agreed product direction and execution sequence.

## 1. Agreed decisions — do not change without approval

1. **LLM provider:** Keep OpenAI. Do not migrate to Gemini or change the model/provider as part of this work.
2. **New patients:** A first-time user can register through the application.
3. **Patient ID:** The system generates a unique Patient ID only after the registration/identity-verification flow succeeds. Typing an arbitrary number is not identity verification.
4. **Identity verification:** Required as part of registration. The exact verification method and required fields are still to be agreed before implementing this part.
5. **Target:** Move toward production readiness, not just a local demo.
6. **Languages:** Support both Arabic and English in the user experience and conversations.
7. **Development discipline:** Work one phase at a time. Inspect the current repository state first, preserve user work, add/update tests, run verification, and summarize the evidence at each phase exit.
8. **Git:** Do not commit or push without explicit user approval. Avoid blanket-staging the whole repository. Never commit .env, credentials, scratch files, or isolated test files.
9. **Data safety:** Do not treat the committed historical appointment CSV or synthetic demo data as current real-clinic availability. Do not place real patient data in demo fixtures.
10. **Scope control:** Do not change unrelated files or rewrite working architecture without a documented reason and approval.

## 2. Current situation and Phase 0 findings

### Repository baseline and working-tree caution

- Current branch: ci/fix-github-actions.
- Local HEAD and origin/ci/fix-github-actions both report ddd8b5854cb7084f26cf9ed83b11fed8f018e5f9 at the time of inspection.
- The working tree reports tests/test_tools.py and toolkit/toolkits.py as modified, plus untracked isolated_test.py through isolated_test6.py, scratch.py, and scratch2.py. The ordinary diff showed no textual changes for the two tracked files during this inspection; do not reset, delete, stage, or otherwise alter these paths without re-inspecting and confirming what they represent.
- No unresolved Git merge conflict was reported by git diff --name-only --diff-filter=U during the inspection.
- Do not infer that a clean-looking diff permits cleanup of the files above.

### Local runtime / actual API error

- Streamlit responds locally at http://127.0.0.1:8501.
- FastAPI /health/ready returned 200 OK after the API was restarted and the graph initialized.
- The configured OPENAI_API_KEY is present in local .env; its value must remain private.
- A direct OpenAI model smoke test failed with HTTP 429 / insufficient_quota / credit_balance_exhausted and the response states the account has no credits remaining.
- Therefore the observed “The clinic service is not ready” message has been traced to the LLM call being unable to run due to OpenAI API credit/quota, not to Gemini configuration or a need to replace the provider.
- Resolution dependency: add API credits / resolve the account's API billing limit, or configure a valid OpenAI API key whose account/project has usable quota. Keep the provider OpenAI. Do not expose keys in logs, messages, screenshots, or Git.
- Focused API and memory test run: 19 passed. A Windows pytest temporary-directory cleanup callback emitted a PermissionError after pytest completed with exit code 0; note it and investigate only if it recurs or impacts verification.
- Last checked listeners: the UI was listening on loopback port 8501 and API on loopback port 8003. Re-check before assuming processes are still running.

### Phase 0 status

**Status: Diagnosis complete; end-to-end model test blocked by OpenAI quota.**

Phase 0 is not considered fully accepted until an actual request from the UI succeeds after valid OpenAI quota is available, or a reproducible service error is documented with logs/request ID. Do not claim that health/readiness 200 OK proves the model has sufficient credits.

## 3. Agreed development phases

The phases below are the execution order for the next development cycle. Existing implementation should be reused where it meets the acceptance criteria; do not rebuild completed components merely to match the new numbering. Production claims require security and operational evidence, not only passing unit tests.

### Phase 0 — Repository audit and unblock the current runtime
**Status: In progress — root cause found; waiting on OpenAI API quota.**

- [x] Confirm branch and compare local HEAD with its upstream.
- [x] Inspect Git conflict state and identify modified/untracked local files to preserve.
- [x] Check Streamlit and FastAPI local endpoints.
- [x] Test OpenAI model invocation without printing credentials.
- [x] Identify HTTP 429 insufficient_quota / credit_balance_exhausted as the current model-call blocker.
- [ ] Restore usable OpenAI API quota/credentials without changing provider/model configuration.
- [ ] Restart the API after quota is available.
- [ ] Send a genuine chat request from Streamlit and confirm a valid agent response.
- [ ] Record final smoke-test result and any remaining error/request ID.
**Exit criteria:** the UI-to-API-to-OpenAI-to-agent flow succeeds, or an exact reproducible blocker is documented. Health endpoint success alone is insufficient.

### Phase 1 — Patient registration and identity requirements
**Status: Not started. This phase must begin with a short design checklist before implementation.**

- Specify the registration fields and minimize collection of personally identifiable information.
- Decide and document the identity-verification method before writing registration logic. Do not invent an OTP provider or treat possession of an arbitrary Patient ID as proof of identity.
- Define duplicate-account handling, verification expiry/retry, lockout/rate limiting, recovery, consent/privacy notice, and account deactivation.
- Define how unique Patient IDs are generated, guaranteed unique, displayed, and recovered without exposing other patients' records.
- Specify Arabic/English validation and user-facing validation/error messages.
- Choose production-appropriate persistent storage and migration strategy before introducing patient accounts; do not store account credentials or identity documents in plaintext.
**Exit criteria:** an agreed registration/verification flow, data model, threat/privacy review, and testable acceptance criteria.

### Phase 2 — Secure patient accounts and Patient ID
**Status: Not started; depends on Phase 1 decisions.**

- Build registration and verification as explicit application flows, with server-side validation.
- Create the patient record and assign a unique Patient ID only after the chosen verification succeeds.
- Require authentication and authorization for patient-specific appointment reads and mutations.
- Keep service-to-service API authentication separate from end-user patient authentication.
- Scope conversation memory and pending appointment actions to an authenticated patient and session; prevent patient-ID guessing from granting access.
- Add tests for registration success/failure, duplicate identities, invalid/expired verification, unauthorized access, cross-patient isolation, ID uniqueness, and account recovery.
**Exit criteria:** account and identity flows pass security-focused tests and never reveal or mutate another patient's data.

### Phase 3 — Bilingual user journey and frontend
**Status: Not started for the new registration journey; current chat UI already exists.**

- Add a clear first-time-user registration entry point and a returning-patient sign-in path.
- Decide the user experience for users who have not completed registration; do not silently invent a registration bypass.
- Support Arabic and English in forms, validation, loading/error messages, conversation prompts, and empty states.
- Review Arabic right-to-left rendering, English left-to-right rendering, switching language mid-session, mobile layout, keyboard navigation, and accessibility.
- Keep patient identifiers masked where appropriate and never show secrets in the UI.
**Exit criteria:** manual browser acceptance scenarios pass in both languages and the onboarding flow is understandable without developer assistance.

### Phase 4 — Core agent workflows and conversation safety
**Status: Existing prototype capability; revalidate after account/authentication changes.**

- Verify FAQ, doctor availability, booking, cancellation, rescheduling, fallback, and human-escalation intent routing.
- Keep FAQ/RAG knowledge separate from transactional appointment state.
- Ensure incomplete requests cause clarification and never trigger an inferred appointment mutation.
- Preserve the server-side pending-action confirmation boundary: the API executes only the validated stored action after a separate exact confirmation.
- Confirm Arabic and English prompts/responses are consistent and safe; do not invent clinic facts or claim an action succeeded before the API confirms it.
- Ensure an unknown/unverified user cannot perform patient-specific actions.
**Exit criteria:** agent/API integration tests pass for supported intents, ambiguity, unsupported questions, pending confirmations, and patient/session isolation.

### Phase 5 — Approved clinic knowledge and appointment data
**Status: Blocked for real-clinic use until data owners approve sources.**

- Keep FAQ content in its dedicated source and appointment availability in its operational data store.
- Obtain clinic-owner approval, effective date, source owner, and review/expiry process for each real FAQ/policy fact.
- Provision a verified current appointment schedule from an authorized source; never label historical or synthetic demo rows as live availability.
- Validate import schema, duplicate/conflicting slots, time zone and date semantics, backup/rollback, and concurrent updates.
- Keep demo fixtures fake, clearly labeled, and isolated from real data.
**Exit criteria:** source ownership/approval is documented; import/retrieval tests pass; unsupported questions and stale/missing data fail safely.

### Phase 6 — Human escalation and conversation lifecycle
**Status: Local queue exists; production handoff and lifecycle controls remain open.**

- Choose a staffed support channel and responsible operational owner; do not claim a human was notified until the integration confirms it.
- Define queue states, retries, failure handling, service-level expectations, and what information can be transferred.
- Define retention/deletion rules for conversations, patient accounts, pending actions, and handoff cases.
- Provide safe account deactivation and appropriate patient-data deletion/export workflows subject to approved policy.
**Exit criteria:** an end-to-end staffed-handoff test and lifecycle/retention tests pass in a controlled environment.

### Phase 7 — Production storage, security, and operations
**Status: Not production ready.**

- Select and implement a transactional operational database appropriate for concurrent appointment booking; do not assume local CSV locks provide multi-host transaction safety.
- Design production persistence for patient accounts, appointments, conversation checkpoints, pending actions, and handoff cases, including migrations and restore procedures.
- Implement end-user authentication/authorization, role-based access, least privilege, secret management, rate limiting, HTTPS/TLS, and secure deployment configuration.
- Define privacy notice/consent where applicable, data minimization, encryption/access policy, audit events, and retention/deletion with the responsible owner.
- Add monitoring, structured non-sensitive logs, alerting, backups, restore rehearsal, incident ownership, load/security testing, and rollback procedures.
- Keep API_ACCESS_TOKEN as service authentication only; never treat it as patient identity.
**Exit criteria:** security/privacy/operations review is approved, data recovery is demonstrated, and release-blocking risks have owners and evidence-based closure.

### Phase 8 — Full verification, deployment, and release decision
**Status: Not started for the new product direction.**

- Add/update tests for every new registration, authentication, authorization, bilingual, database, and end-to-end behavior.
- Run the focused tests, full pytest suite, compile checks, dependency checks, Compose validation, and container build.
- Review changes for secrets and accidental staging of .env, real data, scratch files, or isolated tests.
- Perform manual UI acceptance in Arabic and English, responsive layouts, keyboard accessibility, error recovery, and service restart scenarios.
- Deploy first to an isolated staging environment with synthetic data; verify health, authentication, migration, monitoring, backup/restore, and rollback.
- Release for real-patient use only after clinic data, identity/security, privacy, data storage, human escalation, and operational approvals are complete.
**Exit criteria:** all release checklist items have named owners and evidence; no unresolved critical/high risk remains; user explicitly approves the release.

## 4. Rules for phase execution

For each phase:

1. Inspect current files, Git status, and this plan before editing.
2. State the exact scope, affected files, assumptions, risks, and acceptance tests.
3. Make only changes belonging to the selected phase; preserve existing user changes.
4. Add/update tests alongside implementation.
5. Run focused tests first, then the full suite and applicable compile/dependency/build checks.
6. Inspect diffs and ensure secrets, .env, scratch files, isolated test files, and real patient data are not staged.
7. Update DEVELOPMENT_PLAN.md and ROADMAP.md with verified status, commands, pass/fail results, warnings, and blocked dependencies.
8. Report the result and wait for approval before starting the next phase.
9. Never commit, push, delete or reset local work without explicit approval.

## 5. Immediate next action

**First task:** resolve OpenAI API quota/billing outside the repository, while keeping the OpenAI provider unchanged. Then rerun a real Streamlit-to-API chat smoke test. Do not implement new registration or unrelated code during this unblock step.

After Phase 0 passes, start Phase 1 by agreeing the registration fields and identity-verification method. Production patient registration must not be implemented by inventing verification channels or relying on a patient-entered number alone.

## 6. Progress log

| Date | Phase | Result | Next dependency |
|---|---|---|---|
| 2026-10-15 | Phase 0 | Branch/upstream baseline matched; no unresolved Git conflicts reported; API readiness returned 200; targeted API/memory tests passed 19/19; direct OpenAI call returned 429 insufficient_quota / credit_balance_exhausted. | Restore usable OpenAI API quota and rerun full UI-to-agent chat smoke test. |
| 2026-10-15 | Plan | User confirmed OpenAI stays, patient self-registration creates a Patient ID after identity verification, production-readiness target, Arabic and English. | Confirm identity-verification method and registration fields in Phase 1. |

## 7. Links and existing project documents

- ROADMAP.md — repository-wide phase history and implementation evidence.
- docs/PRODUCTION_READINESS.md — current production limitations and operational/security checklist.
- docs/STREAMLIT_UI_ACCEPTANCE.md — manual UI acceptance cases.
- deployment/demo_data/README.md — isolation and limitations of synthetic demo fixtures.
- Repository: https://github.com/moamedmer68-commits/clinic-ai-customer-service

**Important:** This plan is an execution guide, not evidence that its phases are implemented or that the application is production ready. Change a phase to Completed only after its acceptance criteria have been tested and the evidence recorded.


### 2026-10-18 - Phase 10 verification checkpoint
- Reviewed this execution plan, `ROADMAP.md`, `docs/PRODUCTION_READINESS.md`, and `docs/CI_CD.md` before verification.
- Commit `71e76568fd4f4eb68d248670a0827d5f9d316d95` has a successful hosted GitHub Actions run #18, including the CI container image build: https://github.com/moamedmer68-commits/clinic-ai-customer-service/actions/runs/39129199285
- Local verification on the same working tree: full suite 120 passed in 7.74s; compileall passed; `pip check` found no broken requirements; `docker compose config --quiet` passed; `git diff --check` passed.
- Docker Desktop's Linux engine pipe was unavailable during this checkpoint, so local Compose runtime smoke could not be repeated. Hosted CI image build is confirmed; local service startup is not claimed for this run.
- Phase 10 is not complete: the production release checklist still requires clinic-approved FAQ/current schedule, end-user identity/authentication and authorization, operational privacy/security/retention decisions, transactional production persistence, a staffed escalation channel, backup/restore, security/load testing, manual UI accessibility/responsive acceptance, and an approved deployment/TLS/rollback plan. The known OpenAI quota blocker also prevents claiming a successful real UI-to-agent model smoke test.
- User changes and scratch/isolated files were preserved. No secrets or patient data were staged; no commit/push performed.


### 2026-10-18 — Repository organization checkpoint
- Moved eight local exploratory scripts (`isolated_test.py` through `isolated_test6.py`, `scratch.py`, and `scratch2.py`) from the repository root into `dev/experiments/`; added a README clarifying these are exploratory scripts, not maintained automated tests. Their contents were preserved.
- Kept runtime/import entrypoints (`agent.py`, `main.py`, `streamlit_ui.py`, `knowledge_base.py`, `ui_helpers.py`) at the root because the current Dockerfile, tests, and documented commands depend on those paths. A broader `src/` migration is deferred until it can be handled as a dedicated refactor.
- Verification after the move: full pytest suite — 120 passed in 7.45s; compile check passed; `docker compose config --quiet` passed; `git diff --check` passed (only existing LF/CRLF warnings).
- Existing modifications in `ROADMAP.md`, this plan, `tests/test_tools.py`, and `toolkit/toolkits.py`, plus `.vscode/` and the phase audit, were preserved. No secrets were read; no commit or push performed.
- Next execution dependency remains Phase 0: restore usable OpenAI API quota and complete a real Streamlit-to-API-to-agent chat smoke test before implementing registration/authentication phases.


### 2026-10-18 — Phase 0 runtime recheck
- Re-read the Phase 0 acceptance criteria before acting. Rebuilt and started the local Compose stack with `docker compose up -d --build`; both API and UI images built successfully.
- Runtime evidence: API container reached Docker `healthy`; `GET /health/live` returned HTTP 200; `GET /health/ready` returned HTTP 200; Streamlit root `GET /` returned HTTP 200 after startup.
- This confirms the containers and web endpoints start, but it does **not** prove the UI-to-agent OpenAI call succeeds. The previously recorded direct OpenAI smoke test failed with HTTP 429 `insufficient_quota` / `credit_balance_exhausted`. No real model response is claimed in this recheck.
- Phase 0 remains **blocked on usable OpenAI API quota**. Once the account/project has quota, rerun a genuine chat request through the UI and record the response or sanitized error/request ID. Keep the OpenAI provider unchanged.
- No application code, `.env`, or secrets were read or changed. Existing local modifications and untracked files were preserved. No commit, push, or merge performed.


### 2026-10-18 — Phase 0 genuine API-to-agent smoke test
- Rebuilt/started Compose and verified API readiness and Streamlit root as recorded above.
- Sent a synthetic, non-patient smoke request from inside the UI container to the API using the configured service credential without displaying or reading secret values: `POST /execute`, message `Hello, I need help with an appointment`, synthetic ID `9123456`, session `phase0-smoke-20261018`.
- Result: HTTP 500, request ID `d96182df-a964-458b-94cb-a05ce2445b12`, safe API error `agent_execution_failed`. Sanitized API logs for that request show three OpenAI Chat Completions HTTP 429 responses and the explicit cause `insufficient_quota` / `credit_balance_exhausted` (“no credits remaining”). This is a reproduced end-to-end blocker, not a health-check failure.
- Phase 0 remains blocked until OpenAI API billing/quota is restored. No provider/model change or fallback was introduced. The API and UI containers remain running.
- No app code, `.env`, or secret values were read/changed; the test used only synthetic input. Existing local modifications preserved; no commit/push/merge.


### 2026-10-18 — Phase 2 patient-account implementation checkpoint
- Implemented patient_accounts.py using SQLAlchemy models for patient accounts and opaque sessions. Passwords are salted and PBKDF2-HMAC-SHA256 hashed; raw session tokens are returned only at login and only their SHA-256 hashes are stored. Sessions expire after 12 hours and logout revokes the token.
- Added API flows: POST /patients/register (creates pending_review account; no Patient ID), staff-only pending queue and approval routes, POST /patients/login, GET /patients/me, and POST /patients/logout. An 8-digit Patient ID is generated only after approval; duplicate email registration is rejected.
- Added authenticated-patient enforcement to POST /execute when PATIENT_AUTH_REQUIRED=true (default and enabled in Compose). Requests without a valid patient session receive 401; a supplied patient ID that differs from the authenticated account receives 403. API_ACCESS_TOKEN remains a separate service credential.
- Added PostgreSQL service and persistent named volume to Compose, PATIENT_DATABASE_URL, pinned SQLAlchemy/PostgreSQL driver dependencies, .env.example settings, and ignored local account DB path. Existing application storage for appointments and conversations is not migrated by this phase.
- Added 5 focused tests for pending approval, Patient ID issuance timing, duplicate registration, staff authorization, login/me/logout/revocation, invalid credentials, and rejecting unauthenticated or mismatched patient access.
- Important limitation: staff approval currently uses a separately configured STAFF_REVIEW_TOKEN shared secret, not individual staff accounts/roles. Do not expose the review endpoints publicly; replacing this with authenticated staff identity/RBAC, rate limiting, lockout, database migrations, privacy review, and operational controls remains required before production.
- Phase 2 remains IN PROGRESS, not production-ready. The existing Streamlit UI has not yet been updated to provide registration/login and send the patient bearer token; this is Phase 3 work, so chat through the current UI will be denied by the Compose API until that integration is implemented. OpenAI provider/model unchanged. No commit or push.


### Phase 2 verification result — 2026-10-18
- Focused patient-account suite: 5 passed in 7.51s.
- Full suite with pinned SQLAlchemy 2.0.38 and psycopg 3.2.5 installed: 125 passed in 19.15s.
- compileall passed; pip check reported no broken requirements; docker compose config --quiet passed; git diff --check passed (only existing LF/CRLF warnings).
- Container image rebuild was attempted, but the build remained at Docker Hub metadata retrieval for python:3.12-slim without further output and was stopped; container build/runtime against PostgreSQL is therefore not verified in this checkpoint.
- Phase 2 remains in progress because the UI is not integrated with patient login, staff review still uses a shared token, and production security/operational criteria remain open.
