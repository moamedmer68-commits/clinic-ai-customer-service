# Phase Status Audit — 2026-10-18

## Scope and evidence

Reviewed `ROADMAP.md`, `docs/DEVELOPMENT_PLAN.md`, `docs/PROJECT_AUDIT_AND_ROADMAP.md`, `docs/PRODUCTION_READINESS.md`, `docs/CI_CD.md`, and `docs/STREAMLIT_UI_ACCEPTANCE.md`. Checked the current Git branch/status, the existing local environment without reading secrets, local verification commands, and the hosted GitHub Actions run for commit `71e76568fd4f4eb68d248670a0827d5f9d316d95`.

## Verification results

- Local full suite on the current working tree: 120 passed in 7.74 seconds (`.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-phase10-final`). This includes pre-existing local edits in `tests/test_tools.py` and `toolkit/toolkits.py`; it is not an exact checkout of the pushed commit.
- `compileall`: passed.
- `pip check`: no broken requirements.
- `docker compose config --quiet`: passed.
- `git diff --check`: passed; Git emitted expected LF/CRLF working-copy notices for the two documentation files.
- Hosted GitHub Actions run #18 for pushed commit `71e76568fd4f4eb68d248670a0827d5f9d316d95`: success, including hosted CI container image build. https://github.com/moamedmer68-commits/clinic-ai-customer-service/actions/runs/39129199285
- Local Docker runtime check: not run successfully because Docker Desktop's Linux engine pipe is unavailable.
- Local services: no listener found on ports 8003 or 8501 during this audit. The API/UI were therefore not available for a live UI-to-agent smoke test in this check.
- `.env` exists; its contents were not read or printed. Canonical `data/clinic_faq.json` is 7 bytes and remains effectively empty. Demo FAQ fixture is separate and must not be treated as clinic-approved knowledge.
- Working branch is `fix/phase-0-openai-quota-smoke-test`, HEAD `71e7656`, tracking the corresponding origin branch. No commit/push/merge was performed during this audit. Existing user changes and scratch files were preserved.

## Status by the legacy implementation roadmap (`ROADMAP.md`)

| Phase | Status after audit | Evidence / remaining acceptance work |
|---|---|---|
| 0 — Repository audit | Completed | Initial architecture/risk audit documented. Revisit when architecture or scope changes. |
| 1 — Data integrity | Completed for local prototype | Appointment data invariants, locking/atomic replacement, reschedule safety, and tests are documented. CSV is not adequate shared transactional storage for multi-host production. |
| 2 — Backend reliability | Completed for prototype | API validation, safe error envelopes, request IDs, readiness/liveness and tests documented; production monitoring still belongs to Phase 10. |
| 3 — Intent routing | Completed for prototype | Routing/clarification/bounded execution tests exist. Revalidate after patient authentication is implemented. |
| 4 — FAQ agent | Software complete; real-clinic activation blocked | Strict source validation and grounded fallback exist. Clinic-approved FAQ source is missing; canonical FAQ remains empty. Synthetic FAQs are not approved clinic facts. |
| 5 — Appointment agent integration | Completed for prototype | Tool/routing/mutation tests and API-side exact confirmation gate documented. No patient identity verification; CSV storage remains prototype-grade. |
| 6 — Conversation memory | Completed for prototype | Multi-turn persistence/isolation tests and SQLite checkpointer documented. Automated retention/deletion and multi-host operation remain open. |
| 7 — RAG knowledge base | Engineering complete; real-clinic activation blocked | Ingestion/index/retrieval and synthetic evaluation exist. Semantic retrieval quality against approved clinic content is not verified because approved corpus and usable embedding quota are missing. |
| 8 — Human escalation | Completed for local queue only | Local SQLite cases/status and truthful pending responses exist. No staffed external notification/contact integration or operator access controls. |
| 9 — Frontend chat | Implemented; manual acceptance open | AppTest coverage and Arabic/English UI polish exist. Browser/mobile, keyboard, accessibility, and live API acceptance are not verified. |
| 10 — Production readiness | In progress; not safe for real patient data | Runtime security scaffolding, Compose, pinned manifests, and CI build exist. Authentication, privacy/security approvals, transactional storage, staffed handoff, backup/restore, load/security tests, staging, deployment/rollback and manual UI acceptance remain. |

## Status by the newer product execution plan (`docs/DEVELOPMENT_PLAN.md`)

This plan uses a different phase numbering and must not be silently conflated with the legacy implementation roadmap above.

| New phase | Status after audit | Evidence / remaining acceptance work |
|---|---|---|
| 0 — Runtime unblock | Blocked / in progress | Previous direct OpenAI call returned 429 `insufficient_quota` / `credit_balance_exhausted`. No local API/UI listeners were running during this audit. Restore valid quota, restart services, then complete a real UI-to-agent smoke test. |
| 1 — Registration and identity requirements | Not started | Registration fields, verification method/provider, threat/privacy review, duplicate/recovery rules and acceptance criteria require decisions before implementation. |
| 2 — Secure patient accounts and Patient ID | Not started; depends on Phase 1 | No verified patient registration/authentication flow established by the current plan. Patient ID alone must not grant access. |
| 3 — New bilingual onboarding journey | Partial only for existing chat UI | Existing bilingual chat UI exists; registration/sign-in onboarding, manual RTL/LTR, keyboard and mobile acceptance remain. |
| 4 — Core workflows and safety | Existing prototype; revalidation required | Existing tests and deterministic confirmation gate exist. Re-run integration/security tests after account/authorization work. |
| 5 — Approved clinic data | Blocked for real clinic | No clinic-approved FAQ or verified current schedule source supplied. Historical/synthetic rows cannot be presented as live availability. |
| 6 — Human escalation/lifecycle | Local queue only | Staffed channel, notification confirmation, queue ownership/retry/SLA, retention/deletion and lifecycle tests remain. |
| 7 — Production storage/security/operations | Not production ready | Transactional database, end-user auth/authorization, TLS, managed secrets, rate limits, audit/retention, monitoring, backups/restore and incident ownership remain. |
| 8 — Full verification/deployment/release | Not started for the new direction | Needs integrated tests, manual UI acceptance, isolated staging, migration/backup/rollback evidence, and explicit release approval after all blockers close. |

## Important plan consistency finding

`ROADMAP.md` and `docs/PROJECT_AUDIT_AND_ROADMAP.md` describe the legacy implementation phases 0–10, while `docs/DEVELOPMENT_PLAN.md` defines a new product cycle with phases 0–8. The phase numbers refer to different work, so a label like “Phase 7 complete” is ambiguous unless the plan is named. Use the legacy roadmap for implementation history and the development plan for patient registration / production-directed next steps. Do not renumber completed work or mark new-product phases complete because similarly numbered legacy work exists.

## Release blockers — keep open until evidence exists

1. Restore usable OpenAI API quota and demonstrate a real Streamlit → API → agent response.
2. Agree and implement patient identity verification, registration, authentication, authorization and cross-patient isolation.
3. Obtain clinic-owner-approved FAQ content and a verified current appointment schedule from an authorized source.
4. Replace or constrain CSV/SQLite stores for production concurrency/multi-host requirements; demonstrate migrations and restore.
5. Establish staffed human handoff, operator access, notification ownership, retention and case lifecycle.
6. Approve privacy/security controls: TLS, managed secrets, rate limiting, access policy, audit, encryption, retention/deletion, monitoring and incident ownership.
7. Complete manual Arabic/English browser, responsive, keyboard/accessibility and live-network UI acceptance.
8. Complete security/load/failure tests, isolated staging, backup/restore rehearsal, deployment smoke checks and rollback rehearsal.
9. Obtain clinic/security/privacy approval and explicit release authorization before any real-patient use.

## Safe next action

Treat this document as an audit snapshot, not a claim that all work is finished. First resolve the Phase 0 OpenAI quota/runtime blocker. In parallel, conduct the Phase 1 identity/registration design checklist before implementing patient accounts. Do not deploy to real patient data, change provider/model, or stage existing user scratch files as part of this audit.
