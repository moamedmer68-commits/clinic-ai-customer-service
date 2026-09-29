# Clinic AI Customer Service — Implementation Roadmap

## Purpose
This document is the source of truth for project scope, phase order, implementation status, verification, and remaining work. Update it whenever a task is started, completed, deferred, or found incomplete. Code existing does not alone mean a phase is complete; acceptance criteria and tests must be satisfied.

## Status legend
- **Completed**: scope and acceptance criteria verified.
- **In progress**: implementation exists, but work or verification remains.
- **Not started**: no implementation verified for this phase.
- **Blocked**: progress depends on resolving a stated issue.

## Project baseline and working rules
- Product: multi-agent clinic customer-service system for FAQs and appointment workflows.
- Stack observed: Python, LangGraph/LangChain, FastAPI, Streamlit, CSV appointment data, SQLite checkpointer.
- Preserve user changes. Do not commit, push, delete data, or modify unrelated files unless explicitly requested.
- Before each phase: inspect code and this roadmap; define checklist, scope, dependencies, and risks.
- Implement only the selected phase; add/update tests; keep secrets out of source control.
- At phase exit: run focused tests and the full available suite; record commands, results, warnings, and blocked checks.
- Synchronize this roadmap with actual repository state and evidence.

## Phase overview
| Phase | Name | Current status |
|---|---|---|
| 0 | Repository Audit | Completed (baseline audit) |
| 1 | Data Integrity | Completed — acceptance review, integrity hardening, and tests verified |
| 2 | Backend Reliability & Error Handling | Completed — API contract, safe errors, correlation, and tests verified |
| 3 | Customer Service Core & Intent Routing | Completed — explicit intent routing, clarification, bounded execution, and mocked routing tests verified |
| 4 | FAQ Agent | Not started as a dedicated, tested FAQ capability |
| 5 | Appointment Agent Integration | In progress — appointment tools exist; end-to-end verification pending |
| 6 | Conversation Memory | In progress — SQLite checkpointer and unit tests exist; API/UI verification pending |
| 7 | RAG Knowledge Base | Not started |
| 8 | Support & Human Escalation | Not started |
| 9 | Frontend Chat Experience | In progress — basic Streamlit UI exists; conversational UX work pending |
| 10 | Production Readiness | Not started |

## Phase 0 — Repository Audit
**Goal:** Establish architecture, constraints, known defects, and a reproducible baseline.
**Recorded work:** Reviewed repository structure, README, agent/API/UI/tool code, appointment CSV handling, tests, dependencies, and recent Git history.
**Acceptance criteria:**
- [x] Main components, entry points, data files, and dependencies identified.
- [x] Existing tests and known risks documented.
- [x] Roadmap and phase order recorded.
**Exit status:** Completed as an initial audit. Revisit if architecture or scope changes.

## Phase 1 — Data Integrity
**Goal:** Ensure availability lookup, booking, cancellation, and rescheduling use consistent valid data.
**Implemented/evidence observed:** Shared CSV path resolver (APPOINTMENT_CSV_PATH and project data fallback), normalized timestamp parsing, booking/cancellation writing to the same CSV, and tests in tests/test_tools.py for booking, lookup consistency, unavailable slots, cancellation, and time formatting.
**Verified work:** CSV schema, semantic timestamp, duplicate-slot, and availability/patient invariants are rejected safely. Mutations use an exclusive lock file plus atomic replace; rescheduling validates both slots and writes one combined state, so a failed move preserves the old appointment. Tests cover reschedule success/failure, malformed and duplicate CSV, failed writes, reload persistence, and simultaneous booking attempts.
**Limitations:** The CSV lock is appropriate for this local single-host prototype. A shared/network filesystem or multi-host deployment needs transactional database storage before production.
**Acceptance criteria:** mutations preserve invariants; reads reflect persisted changes; failures do not corrupt/release appointments unexpectedly; focused and full tests pass.
**Current status:** Completed. Focused appointment tests and the full suite passed on 2026-09-29.

## Phase 2 — Backend Reliability & Error Handling
**Goal:** Make the FastAPI service predictable, diagnosable, and safe under invalid input/runtime failures.
**Implemented/evidence observed:** backend logging and error-handling work is recorded in commit ab69a3a.
**Verified work:** `create_app` initializes dependencies at startup without preventing an API health response when configuration is missing. `/health` and `/execute` provide a consistent safe error envelope; request validation returns 422, unavailable dependencies return 503, and graph failures return 500 without exposing stack traces. Request IDs are returned in the response/header and included in application logs; patient IDs and session IDs are not logged. API tests cover valid requests, validation, missing configuration, graph failures, and JSON-compatible message serialization.
**Acceptance criteria:** predictable API contract, safe client errors, useful logs, automated API tests pass.
**Current status:** Completed. Focused API tests and the full suite passed on 2026-09-29.

## Phase 3 — Customer Service Core & Intent Routing
**Goal:** Route patient messages reliably and handle unclear/unsupported requests safely.
**Implemented/evidence observed:** The existing LangGraph supervisor now produces a structured semantic intent rather than a direct worker name. The application maps `faq` and `availability` to the existing information agent, and `book`, `cancel`, and `reschedule` to the existing booking agent. `fallback` ends safely with a clarification; it does not claim that a human was contacted (human escalation remains Phase 8).
**Remaining tasks:**
- [x] Define intents: FAQ, availability, book, cancel, reschedule, fallback/escalation.
- [x] Define required entities per intent and clarification behavior for missing details.
- [x] Add deterministic or mocked-LLM routing tests for common, ambiguous, and unsupported requests.
- [x] Guard against loops, repeated tool calls, and premature completion.
- [x] Standardize conversation state and tool-result handoff.
**Acceptance criteria:** documented intents; routing/clarification demonstrated by tests; execution is bounded.
**Intent/entity and clarification contract:**

| Intent | Required details before the specialist can act | Missing-detail behavior |
|---|---|---|
| FAQ | The clinic question | Information agent answers only from its configured capability or asks the patient to clarify the question. Authoritative FAQ content is Phase 4 work. |
| Availability | Date; doctor name or specialization | Information agent asks for the missing date and doctor/specialization. It must not infer a year. |
| Book | Doctor, complete date/time; patient identity is supplied by the API | Booking agent asks for missing doctor or complete date/time before it can call a tool. Confirmation design is Phase 5 work. |
| Cancel | Doctor and complete date/time; patient identity is supplied by the API | Booking agent asks for the missing appointment identifiers before it can call a tool. |
| Reschedule | Doctor, old complete date/time, new complete date/time; patient identity is supplied by the API | Booking agent asks for every missing old/new appointment detail before it can call a tool. |
| Fallback | A request within the supported service scope | Supervisor returns a bounded clarification covering supported FAQ, availability, and appointment actions. Unsupported or medical-advice requests are not guessed. |

**Verified work:** The supervisor extracts the newest `HumanMessage` from persisted history, keeps `intent`, `query`, and routing reasoning in shared state, and uses the normal message handoff to the existing worker nodes. After a named worker response, the supervisor ends the current graph invocation, preventing a repeated worker/tool cycle; the API recursion limit remains a secondary bound. Mocked tests cover all supported intent destinations, a multi-turn follow-up, fallback clarification, and the no-repeat-worker guard.
**Current status:** Completed. Focused routing tests passed on 2026-09-29; full-suite verification is recorded below.

## Phase 4 — FAQ Agent
**Goal:** Answer clinic service questions from approved, maintained clinic information.
**Tasks:**
- [ ] Define FAQ scope and authoritative content (hours, location, services, policies, preparation, payment/insurance if applicable).
- [ ] Implement dedicated FAQ capability with boundaries and fallback for absent information.
- [ ] Ground answers; do not invent clinic policies or provide unsupported medical advice.
- [ ] Test known answers, paraphrases, missing answers, and out-of-scope medical questions.
- [ ] Integrate FAQ intent into supervisor; document content update process.
**Acceptance criteria:** answers supported by configured source content; unknown answers transparently deferred; routing/tests pass.
## Phase 5 — Appointment Agent Integration
**Goal:** Deliver complete appointment workflows through the agent/API using Phase 1 integrity guarantees.
**Implemented/evidence observed:** lookup, booking, cancellation, and rescheduling tools exist in toolkit/toolkits.py; booking agent/node exists.
**Remaining tasks:**
- [ ] Define tool contracts, required fields, confirmations, and user-facing outcomes.
- [ ] Integrate lookup/book/cancel/reschedule with clarification for missing doctor/date/time/patient ID.
- [ ] Require confirmation before consequential mutations where appropriate.
- [ ] Add mocked-agent/API integration tests for each workflow and failure path.
- [ ] Verify errors propagate safely and appointment state remains consistent.
**Acceptance criteria:** supported appointment flows work end-to-end through API; outcomes are accurate; success/failure tests pass.

## Phase 6 — Conversation Memory
**Goal:** Preserve context across turns while isolating patients and sessions.
**Implemented/evidence observed:** SQLite checkpointer configured in API, session/thread ID helper in utils/session.py, Streamlit session handling, dependency pin, and tests in tests/test_memory.py for isolation and persistence.
**Remaining tasks:**
- [ ] Verify multi-turn memory through actual FastAPI requests, not only isolated graph tests.
- [ ] Verify Streamlit session creation, continuation, and new-conversation behavior.
- [ ] Confirm patient/session isolation; avoid raw patient identifiers in thread IDs/logs.
- [ ] Define retention, deletion, backup, and SQLite concurrency expectations.
- [ ] Test restart persistence and malformed/expired sessions.
**Acceptance criteria:** intended multi-turn context persists; sessions are isolated; restart behavior tested; retention/privacy documented.

## Phase 7 — RAG Knowledge Base
**Goal:** Retrieve current clinic knowledge with traceable grounding for FAQ/policy answers.
**Tasks:**
- [ ] Select approved documents and define content ownership/update process.
- [ ] Implement ingestion, parsing, chunking, metadata, embeddings, and vector-store persistence.
- [ ] Implement retrieval with source filters/configurable top-k; evaluate relevance and missing-answer behavior.
- [ ] Return citations/source references where practical.
- [ ] Create evaluation set for answer correctness, retrieval relevance, hallucination resistance, and updates.
- [ ] Integrate retrieval with FAQ only after evaluation criteria are met.
**Acceptance criteria:** repeatable ingestion; documented retrieval evaluation; grounded answers; safe fallback when evidence is insufficient.

## Phase 8 — Support & Human Escalation
**Goal:** Transfer unresolved, sensitive, or user-requested cases to a human with useful context.
**Tasks:**
- [ ] Define triggers, user notice/consent, business hours, and response-time expectations.
- [ ] Choose handoff channel/integration or explicit local queue for prototype.
- [ ] Create concise handoff summary containing only necessary conversation details.
- [ ] Track escalation status; do not claim a human responded before confirmation.
- [ ] Test requested escalation, unresolved questions, errors, and unavailable support.
**Acceptance criteria:** explicit/testable escalation; privacy-minimized context; truthful status messaging.

## Phase 9 — Frontend Chat Experience
**Goal:** Provide clear, accessible multi-turn chat and reliable feedback.
**Implemented/evidence observed:** basic Streamlit UI exists and calls FastAPI endpoint.
**Remaining tasks:**
- [ ] Provide chat transcript and conversation controls beyond the basic form.
- [ ] Display loading, validation, service errors, tool outcomes, and escalation state.
- [ ] Preserve session state; support starting a new conversation.
- [ ] Improve validation, accessibility, responsive layout, and safe rendering.
- [ ] Add UI tests or documented manual acceptance scenarios.
**Acceptance criteria:** users complete multi-turn FAQ/appointment tasks with clear status/errors; session behavior verified.

## Phase 10 — Production Readiness
**Goal:** Prepare secure, observable, repeatable deployment and operation.
**Tasks:**
- [ ] Define deployment target, environment configuration, secrets management, and startup checks.
- [ ] Reproduce dependencies/environment; resolve native/heavy dependency installation constraints.
- [ ] Add Docker/CI if selected for deployment; automate linting and tests.
- [ ] Review authentication/authorization, patient-data minimization, retention, encryption, and access controls.
- [ ] Add health/readiness checks, metrics/logging, timeouts, retries, rate limits, and graceful shutdown.
- [ ] Define backup/recovery; document CSV-to-transactional-storage migration if concurrency requires it.
- [ ] Perform security/failure/load checks; document limitations and release/rollback procedure.
**Acceptance criteria:** reproducible deployment; automated checks pass; operational/security controls verified; recovery plan exists.

## Execution log

Append a dated entry after each work session: phase, files changed, exact test commands/results, warnings, unresolved issues, and next action. Do not mark a phase complete until all acceptance criteria are satisfied.

### Phase 3 execution entry - 2026-09-29
- Changed `agent.py`, `prompt_library/prompt.py`, `tests/test_routing.py`, and this roadmap. The existing supervisor and two existing specialist nodes were retained. Structured routing now classifies `faq`, `availability`, `book`, `cancel`, `reschedule`, or `fallback`; supported intents use the existing nodes and fallback returns a safe clarification.
- Multi-turn behavior: the supervisor extracts the latest patient message from persisted LangGraph history instead of only reading a one-message state. It retains that query, intent, and reasoning in state. It ends after a worker response to prevent repeated routing/tool cycles during the same invocation.
- Date behavior: removed the hardcoded 2024 instruction from both specialist prompts. Specialists now require an explicit complete patient date when needed and do not infer a year. The sample schedule remains 2024 data; availability for other years depends on the configured data set.
- Focused command: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_routing.py -q -p no:cacheprovider` - 4 passed. The tests use a fake structured model; no external API call was made.
- Full command: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider` - 25 passed, 73 warnings.
- Warnings/blockers: `git diff --check` reports pre-existing trailing whitespace in `tests/test_memory.py`; it is outside Phase 3 and was not changed. The known full dependency-install limitation remains: pinned `chroma-hnswlib` needs Microsoft Visual C++ 14.0+ Build Tools. Tests use the existing reduced `.venv`. Dedicated grounded FAQ content (Phase 4), appointment confirmation/end-to-end flows (Phase 5), API-level memory verification (Phase 6), and human escalation (Phase 8) remain unresolved and out of Phase 3 scope.
### Initial baseline entry — 2026-09-29
- Phase 0: repository audit documented; completed as baseline.
- Phase 1: data-integrity changes are present in repository history; current suite previously reported 11 passing tests (2 memory + 9 appointment-tool tests). Atomic rescheduling and concurrent booking remain unverified.
- Phase 2: logging/error-handling work exists in commit ab69a3a; acceptance review and API tests remain.
- Phase 6: SQLite conversation-memory implementation exists in commit 8d161b4; two memory tests passed, but API/UI multi-turn integration remains to be verified.
- Environment note: full pinned requirements installation previously failed because chroma-hnswlib required Microsoft Visual C++ 14.0+ Build Tools. A reduced test dependency environment passed tests; this does not prove the full application environment installs cleanly.
- Existing working-tree modifications and scratch/isolated test files were present before this roadmap was added. They were left untouched.
- Next planned work: finish Phase 1 acceptance review, then Phase 2 backend reliability review/tests. No commit or push performed for roadmap creation.
### Phase 1 and 2 verification entry — 2026-09-29
- Phase 1 files changed: `toolkit/toolkits.py`, `data_models/models.py`, `tests/test_tools.py`. Added CSV schema/state validation, semantic date validation, atomic writes, local lock-file concurrency control, and atomic rescheduling. Focused command: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_tools.py -q -p no:cacheprovider` — 14 passed.
- Phase 2 files changed: `main.py`, `utils/llms.py`, `tests/test_api.py`. Added app factory/lifespan configuration handling, `/health`, safe error envelope/statuses, request ID correlation, and API tests. Focused command: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_api.py -q -p no:cacheprovider` — 5 passed.
- Full command: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider` — 21 passed. Warnings: FastAPI TestClient reports deprecated `httpx` integration; existing memory tests emit 72 Pydantic deprecation warnings. No full requirements installation was attempted; the existing reduced `.venv` was used because the known `chroma-hnswlib` native-build constraint remains.
- Remaining operational limitation: CSV locking is not a production substitute for transactional multi-host storage. No commit, push, deletion, or edits to existing scratch files were performed.

### Execution entry — 2026-09-29 (Phase 1 and Phase 2)
- Phase 1 completed: added CSV schema/state validation, duplicate-slot rejection, cross-process lock-file protection for mutations, atomic file replacement, and atomic rescheduling. Added tests for reschedule success/failure, malformed/duplicate data, concurrent booking, persistence, and failed writes.
- Phase 2 completed: added a health endpoint, bounded request message length, request ID propagation, safe API error envelopes, startup dependency handling, and API tests for health/configuration, valid request, validation, graph failure, and JSON-compatible message content. Validation details now omit raw input/context values.
- Verification: `python -m pytest tests/test_tools.py -q -p no:cacheprovider` — 14 passed; `python -m pytest tests/test_api.py -q -p no:cacheprovider` — 5 passed; `python -m pytest -q -p no:cacheprovider` — 21 passed, 73 warnings.
- Warnings: 72 Pydantic deprecation warnings from the installed LangChain/Pydantic combination and one Starlette TestClient/httpx deprecation warning. No test failures.
- Environment limitation: the full pinned requirements installation previously failed because chroma-hnswlib needs Microsoft Visual C++ 14.0+ Build Tools. Tests ran using the existing reduced virtual environment; a complete application dependency install and live OpenAI-backed request were not verified.
- Phase 1 limitation: lock-file CSV coordination is intended for a single host/local prototype; use a transactional database for multi-host or production concurrency.
- No commit or push performed. Existing unrelated modifications and untracked scratch files were preserved.
- Next phase: Phase 3 — Customer Service Core & Intent Routing.
