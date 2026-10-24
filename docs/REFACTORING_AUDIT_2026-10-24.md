# Codebase Refactoring Audit — 2026-10-24

## Scope and evidence

Repository: `clinic-ai-customer-service`; branch: `خطة-التطوير`. The working tree already contained modifications to `main.py`, `streamlit_ui.py`, `tests/test_streamlit_ui.py`, `ROADMAP.md`, and `docs/DEVELOPMENT_PLAN.md`, plus untracked reports/design documentation. These were preserved. No commit, push, reset, or deletion was performed.

Reviewed the README, implementation roadmap, development plan, runtime/test dependency manifests, Dockerfile, and the main execution modules (`main.py`, `agent.py`, `streamlit_ui.py`, `patient_accounts.py`, `knowledge_base.py`, `security_controls.py`, `ui_helpers.py`, `toolkit/`, `support/`, `data_models/`, `utils/`, and `prompt_library/`) to map entry points and risk boundaries.

## Architecture observed

- FastAPI (`main.py`) exposes health, patient authentication, and `/execute` API routes.
- LangGraph orchestration (`agent.py`) routes to FAQ, appointment information/booking, and handoff paths. Prompt/routing behavior is under `prompt_library/`.
- Appointment tools (`toolkit/toolkits.py`) operate on the configured CSV and must retain its validation and mutation safeguards.
- FAQ retrieval/indexing is implemented in `knowledge_base.py`; canonical clinic FAQ data is intentionally empty pending approval.
- Patient accounts/sessions use SQLAlchemy (`patient_accounts.py`); login throttling/audit controls live in `security_controls.py`.
- Pending appointment actions and human handoff are separate SQLite workflows under `support/`.
- Streamlit (`streamlit_ui.py`) owns bilingual onboarding/chat presentation; `ui_helpers.py` contains UI validation/formatting helpers.
- Dockerfile copies root entry points and package directories explicitly, so moving modules or deleting files based only on static import search risks breaking container builds and framework imports.

## Findings and priority

### Safe cleanup
- README instructions still described staff approval and pending-review registration after the product decision changed to direct registration. Updated the relevant onboarding/API documentation to describe immediate Patient ID issuance and automatic sign-in; legacy staff endpoints are explicitly labeled as legacy.
- No other code deletion was made without stronger evidence. Comments/prompts and explicit safety checks were retained where they document agent behavior, authorization, or transactional boundaries.

### Duplication / structural changes
- The current implementation is split into reasonably distinct API, agent, retrieval, account, tool, handoff, and UI modules. No broad module moves or agent merges were justified by the audit: Docker COPY rules, tests, and imports rely on the existing paths.
- The next high-value consolidation is to reconcile the registration contract and its tests, then review repeated API error/session handling with focused tests before extracting any shared helper.

### Dependencies
- `requirements-runtime.txt` is a pinned, comparatively minimal production runtime manifest. `requirements-test.txt` layers pytest and httpx over it.
- `requirements.txt` is a large historical/research environment manifest with many libraries not obviously used by the current production entry points. It was not pruned because it is also consumed by `setup.py` as `install_requires`; removing entries without tracing the packaging contract could break editable installs, notebooks, experiments, or downstream users. Ruff is not installed in the current virtual environment, so no Ruff result is claimed.

### Risky / deferred
- Registration API/UI were already modified to remove identity verification and staff approval. Existing account tests still assert the old pending-review contract; changing tests merely to silence failures is not acceptable. Rewrite those tests around the approved behavior while preserving duplicate-email, password/session, rate-limit, unique-ID, and cross-patient-isolation coverage.
- `streamlit_ui.py` contains Arabic strings that appear mojibaked in the current source. Avoid a whole-file encoding rewrite; repair through a focused encoding-aware change and validate the Arabic UI.
- Existing pending-review accounts require a documented migration/product decision before any bulk approval; no data migration was run.
- OpenAI real-model smoke remains blocked by the previously documented insufficient-quota error. Docker runtime and manual browser/accessibility acceptance were not demonstrated in this audit.

## Validation baseline

Command: `.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-refactor-baseline`

Observed result: **10 failed, 126 passed in 14.81s**. All ten failures are in `tests/test_patient_accounts.py` and arise from tests expecting HTTP 202 / `pending_review` / staff approval while the current registration endpoint returns HTTP 201 and creates a session. This is a known contract/test mismatch, not evidence that the refactor passed.

`python -m ruff` could not run because Ruff is not installed (`No module named ruff`). No new dependency was installed. The focused compile and `git diff --check` checks were run separately; the latter reports only existing LF/CRLF warnings. Docker engine availability and live OpenAI quota were not re-established here.

## Execution plan

1. Resolve the direct-registration contract with API/UI/account tests without weakening authorization or deleting legacy account support accidentally.
2. Run focused account/UI tests, then full pytest, compile checks, `pip check`, Compose config validation, and `git diff --check`.
3. Run a static unused-import/dead-code audit with an available tool or targeted AST analysis; add no linter dependency solely for this cleanup.
4. Only then consider duplicate-helper extraction or dependency removal where call-site and packaging evidence proves safety.
5. Keep agent prompts, routing, tool schemas, confirmation gates, RAG behavior, and handoff transitions unchanged unless dedicated regression tests justify a behavior-preserving edit.

This audit is not a claim that the entire refactor is complete or the application is production-ready.
