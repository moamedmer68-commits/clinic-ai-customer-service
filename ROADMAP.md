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
| Phase | Name | Current status | Estimated completion |
|---|---|---|---:|
| 0 | Repository Audit | Completed — baseline and current structure reviewed | 100% |
| 1 | Data Integrity | Completed — CSV invariants, guarded mutations, and tests verified | 100% |
| 2 | Backend Reliability & Error Handling | Completed — API contract, safe errors, correlation, and tests verified | 100% |
| 3 | Customer Service Core & Intent Routing | Completed — explicit routing, clarification, bounded execution, and tests verified | 100% |
| 4 | FAQ Agent | Software scope completed — strict source preflight, grounded retrieval, safe no-answer handoff, and tests verified; activation on real clinic facts remains blocked pending owner-approved content | 100% software scope |
| 5 | Appointment Agent Integration | Completed for prototype — specialist tools, confirmation instructions, routing/integration and mutation tests verified | 100% |
| 6 | Conversation Memory | Completed for prototype — API multi-turn/restart persistence, isolation, Streamlit controls, operations guidance verified | 100% |
| 7 | RAG Knowledge Base | Blocked for real-world activation — semantic RAG implementation, persistent vector index, ingestion, source tracking, and synthetic evaluation verified; clinic-approved corpus remains external dependency | 95% |
| 8 | Support & Human Escalation | Completed for local-queue prototype — deterministic triggers, privacy-minimized handoff records, status tracking, truthful responses, and tests verified | 100% |
| 9 | Frontend Chat Experience | Implemented and AppTest verified — transcript, session controls, masked ID validation, service errors, and escalation feedback; manual browser/responsive review remains | 90% |
| 10 | Production Readiness | In progress — API token gate, readiness/liveness checks, pinned runtime/test manifests, Compose/Docker scaffold, hosted CI image build verified, and deterministic server-side mutation confirmation; clinic deployment/security approvals and manual UI review remain | 72% |

**Percentage note:** These are approximate scope-completion estimates based on implemented and verified roadmap criteria, not test coverage or a claim of production readiness. Phases 5–6 are complete only for prototype scope; their listed production limitations remain in Phase 10.

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
**Exit update — 2026-10-13:** Completed the remaining software-side content-publishing safeguard. `validate_faq_source()` now rejects missing/unreadable files, malformed JSON, non-list payloads, empty corpora, and any invalid record; `ingest_faq()` uses it before embedding/saving, so a bad source cannot be silently published as a partial/empty index. Added tests for each failure class and normalized valid metadata. Existing retrieval, source IDs, thresholded no-answer behavior, escalation, and synthetic evaluation remain covered. Real-world FAQ activation is still blocked until a clinic owner supplies and approves the actual facts; the canonical `data/clinic_faq.json` remains intentionally empty.
**Goal:** Answer clinic service questions from approved, maintained clinic information.
**Data review (2026-09-29):** `data/` contains `doctor_availability.csv` (columns: `date_slot`, `specialization`, `doctor_name`, `is_available`, `patient_to_attend`; 4,280 data rows) and no authoritative clinic FAQ facts. The appointment CSV is used by appointment availability/booking workflows and is not treated as a source for clinic hours, address, fees, insurance, or policies. No patient row values were copied into FAQ content.
**Implemented:** Dedicated `faq_node` receives FAQ intent; it reads approved entries from `data/clinic_faq.json`, matches question/keyword terms, returns configured answer text, and safely defers unknown questions. Medical-advice terms trigger a boundary response. FAQ routing is distinct from availability routing. The JSON file is currently an empty list because clinic facts have not been provided/verified.
**Tasks:**
- [x] Define FAQ source format and keep it separate from appointment data.
- [x] Implement dedicated FAQ capability with boundaries and fallback for absent information.
- [x] Ground answers in configured content; do not invent clinic policies or provide unsupported medical advice.
- [x] Test known answers, paraphrases, missing answers, medical-advice boundary, and supervisor routing.
- [ ] Populate and verify authoritative FAQ content (hours, location, services, policies, preparation, payment/insurance if applicable).
- [x] Document the content update process for clinic operators, including strict preflight and index-build commands.
**Acceptance criteria:** answers supported by configured source content; unknown answers transparently deferred; routing/tests pass; clinic content approved. The final content approval criterion remains open.
**Verification:** `python -m pytest tests/test_faq.py tests/test_routing.py -q -p no:cacheprovider` — 8 passed. Full `python -m pytest -q -p no:cacheprovider` — 29 passed, 73 warnings. A pytest temporary-directory cleanup emitted a Windows `PermissionError` during interpreter shutdown after tests; pytest exit code was 0. Existing Starlette/httpx and Pydantic deprecation warnings remain.
## Phase 5 — Appointment Agent Integration
**Goal:** Deliver complete appointment workflows through the agent/API using Phase 1 integrity guarantees.
**Implemented/evidence observed:** lookup, booking, cancellation, and rescheduling tools exist in toolkit/toolkits.py; booking agent/node exists.
**Implemented:** The booking specialist has read-only availability lookup plus a `prepare_appointment_change` tool; it is not given direct book/cancel/reschedule tools. The preparation tool validates and stores an exact candidate action but does not mutate the schedule. The API executes the stored action only after an exact standalone confirmation in the same hashed patient/session thread. Existing mutation functions enforce patient-ID matching for cancellation/rescheduling, prevent double booking, return explicit unavailable/missing/data-error outcomes, and preserve state on failed atomic writes. Supervisor clarification prevents incomplete appointment requests from reaching the specialist.
**Verification:** Added `tests/test_appointment_agent.py` for booking/cancel/reschedule routing, specialist tool availability, confirmation/outcome instructions, and worker response handoff. Existing `tests/test_tools.py` covers booking, cancellation, rescheduling, unavailable/mismatched appointments, persistence, concurrency, and failed writes. API contract/error tests remain in `tests/test_api.py`.
**Acceptance criteria:** supported appointment intents route to the booking specialist; tool contracts validate required date/ID inputs; mutation results are explicit and state integrity is covered by tests; API errors remain safe.
**Current status:** The agent-only confirmation instruction was replaced in Phase 10 by a deterministic API-side pending-action gate. The booking specialist can prepare a proposal but has no direct mutation tools; the API executes the stored operation only after a standalone exact confirmation in the same hashed patient/session thread. Production identity/authentication and transactional storage remain separate release blockers.

## Phase 6 — Conversation Memory
**Goal:** Preserve context across turns while isolating patients and sessions.
**Implemented:** The API uses a stable SHA-256 thread key derived from patient ID and session ID; raw identifiers are not used as checkpoint keys or logged. Streamlit now creates a random session ID, displays chat turns, continues the same session, and offers a new-conversation control. SQLite remains the configured checkpointer.
**Verified:** API-level tests exercise consecutive turns, patient/session isolation, and persistence across app restart using a file-backed SQLite checkpointer. Existing unit coverage verifies stable/scoped non-reversible-looking thread keys. Session IDs are bounded by API schema; no expiration is implemented.
**Operations:** `docs/CONVERSATION_MEMORY.md` documents persistence location, no-expiry prototype behavior, deletion, backup, privacy, single-process SQLite limits, and manual UI acceptance scenarios. Per-patient deletion and automated retention are not implemented; clinic policy must be set before real patient data use.
**Acceptance criteria:** [x] multi-turn context persists; [x] patient/session isolation; [x] restart behavior; [x] retention/deletion/backup/concurrency guidance; [x] UI controls/manual acceptance documented.
**Current status:** Completed for prototype scope. Multi-worker/multi-host SQLite use and automated retention remain production limitations (Phase 10).

## Phase 7 — RAG Knowledge Base
**Goal:** Retrieve current clinic knowledge with traceable grounding for FAQ/policy answers.
**Current implementation:** FAQ records are validated and normalized, embedded with the configured OpenAI embedding model, stored in a persistent file-based vector index (`embeddings.npy` + JSON metadata), fingerprinted for content-aware rebuilds, retrieved by cosine similarity with configurable top-k/source filters/thresholds, and returned as grounded answers with source IDs. A deterministic lexical retriever remains available as a baseline for tests. Appointment workflows remain separate structured CSV/tool operations and are not semantic retrieval.
**Tasks:**
- [ ] Select and load the clinic-approved corpus and define clinic ownership/review/update process before real-world use.
- [x] Implement validated FAQ ingestion, metadata, embeddings, and persistent vector-index storage. FAQ records are already atomic retrieval units, so no generic document splitter is required for the current corpus.
- [x] Implement deterministic lexical retrieval with record validation and explicit no-answer behavior.
- [x] Implement semantic vector retrieval with source-ID filters, configurable top-k, similarity thresholding, and measured missing-answer behavior.
- [x] Return source IDs for matched FAQ entries where configured.
- [x] Create a synthetic evaluation set and deterministic retrieval metrics: hit rate@k, MRR, and no-answer rate.
- [x] Integrate semantic retrieval with the FAQ node using grounded stored answers and fail-closed behavior.
**Acceptance criteria:** repeatable ingestion [x]; documented retrieval evaluation [x]; grounded answers [x]; safe fallback when evidence is insufficient [x]. Remaining release dependency: clinic-owned approved FAQ content and final content/relevance review.

## Phase 8 — Support & Human Escalation
**Goal:** Transfer unresolved, sensitive, or user-requested cases to a human with useful context.
**Implemented:** A local SQLite handoff queue is used for the prototype. The supervisor detects high-confidence explicit human requests, complaints/manager requests, and urgent/severe medical wording before LLM routing. The FAQ node escalates unresolved questions, medical-advice requests, and semantic retrieval errors.
**Tasks:**
- [x] Define triggers, user notice/consent, business hours, and response-time expectations.
- [x] Choose handoff channel/integration or explicit local queue for prototype.
- [x] Create concise handoff summary containing only necessary conversation details.
- [x] Track escalation status; do not claim a human responded before confirmation.
- [x] Test requested escalation, unresolved questions, errors, and unavailable support.
**Prototype policy:** the local queue accepts cases 24/7; no response-time SLA is promised. An explicit human request is the patient's direct escalation consent. Automatic unresolved/sensitive escalation is immediately disclosed to the patient; the prototype stores the case locally and does not transmit it to a third-party contact channel.
**Acceptance criteria:** explicit/testable escalation; privacy-minimized context; truthful status messaging.
**Current status:** Completed for prototype scope. Production handoff still requires an authenticated support channel, operator access control, notification/ownership, retention policy, and an actual human contact path.

## Phase 9 — Frontend Chat Experience
**Goal:** Provide clear, accessible multi-turn chat and reliable feedback.
**Implemented:** Reworked `streamlit_ui.py` with masked patient-ID entry, input bounds validation, chat transcript, loading state, configurable API URL/request timeout, clear service/API error messages, safe Markdown rendering, new-conversation control, and pending human-handoff case display. The API now returns current-invocation escalation status metadata and resets stale escalation state for each new turn. Pure validation/parsing helpers live in `ui_helpers.py`.
**Tasks:**
- [x] Provide chat transcript and conversation controls beyond the basic form.
- [x] Display loading, validation, service errors, tool outcomes, and escalation state.
- [x] Preserve session state; support starting a new conversation.
- [ ] Complete manual browser review for responsive layout, keyboard navigation, and real API/Streamlit interaction.
- [x] Add automated Streamlit AppTest checks and documented manual acceptance scenarios.
**Verification:** `tests/test_ui_helpers.py`, `tests/test_streamlit_ui.py`, and API metadata tests cover ID validation, response extraction, invalid IDs, successful responses, pending escalation, and new-session behavior. Visual/mobile and real-network smoke tests still require a manual run.
**Acceptance criteria:** multi-turn behavior and frontend status/error contracts pass automated tests; manual browser/responsive review remains open.
**Current status:** Implemented for prototype. Manual browser/responsive validation remains; do not claim full accessibility certification.

## Phase 10 — Production Readiness
**Goal:** Prepare secure, observable, repeatable deployment and operation.
**Implemented for the current prototype:**
- `main.py` requires `API_ACCESS_TOKEN` for `POST /execute` by default, compares credentials with `hmac.compare_digest`, rejects missing/invalid tokens, and has an explicit local-only escape hatch that defaults off.
- Request IDs are restricted to a safe allowlist; API responses set `Cache-Control: no-store`. Added `/health/live` and readiness checks.
- OpenAI model configuration now uses environment-controlled bounded timeout/retry settings. Shared `SqliteSaver` invocations are serialized in the single-process prototype to avoid concurrent use of one connection.
- Added curated pinned `requirements-runtime.txt` and `requirements-test.txt` rather than installing the full optional research/CV dependency set for a production runtime.
- Added a non-root `Dockerfile`, `.dockerignore`, `docker-compose.yml`, deployment FAQ template, `.env.example` security/runtime variables, and ignored `runtime-data/` directory. Compose binds API/UI ports to localhost, requires secrets, and mounts separately provisioned runtime data; it never packages the historical appointment CSV.
- CI uses the pinned runtime/test manifests, checks dependency consistency, compiles app/UI/support modules, runs tests, and builds a container image.
- Added `docs/PRODUCTION_READINESS.md` with launch instructions and explicit unresolved release gates.
**Tasks:**
- [x] Define deployment scaffold, environment configuration, secret names, and startup/readiness checks; actual hosting target and secret-store selection remain environment decisions.
- [x] Separate and pin the supported runtime dependency set; complete isolation of every transitive dependency remains a future lock-file improvement.
- [x] Add Docker/Compose and CI compile/test/image-build steps.
- [x] Add service-token gate, patient-data minimization in current flows, readiness/liveness checks, request correlation, bounded OpenAI timeouts/retries, and local SQLite invocation serialization.
- [ ] Add end-user authentication/authorization, rate limiting, managed secrets, TLS/reverse proxy, encryption/access policy, retention/deletion, and operational alerting.
- [ ] Define backup/recovery and migrate from CSV/SQLite prototype storage to transactional/shared persistence where concurrency or multi-host deployment requires it.
- [ ] Validate external human handoff/notification with an actual staffed support channel.
- [ ] Perform failure/load/security checks, manual UI accessibility/responsive review, deployment smoke tests, and release/rollback rehearsal.
**Verification:** Full local test suite passed after the API authorization changes; `pip check` passed; `docker compose config --quiet` parsed successfully using dummy environment values. A local `docker build` could not run because Docker Desktop's Linux engine pipe was not running, so the container image itself is not yet verified. CI now builds the image on hosted runners.
**Acceptance criteria:** prototype security/configuration and CI/container scaffolding verified; operational/security controls and environment-specific release gates remain open.
**Current status:** In progress / not safe for real clinic data. Phase 7 still requires clinic-approved FAQ content; deployment needs an authorized current appointment schedule, real secrets, a staffed human-support channel, and privacy/security sign-off.

## Execution log

Append a dated entry after each work session: phase, files changed, exact test commands/results, warnings, unresolved issues, and next action. Do not mark a phase complete until all acceptance criteria are satisfied.

### Phase 6 execution entry — 2026-09-29
- Updated `streamlit_ui.py` with random session initialization, visible user/assistant transcript, continued API session, new-conversation control, input validation, request timeout, and safe request failure display. Removed `verify=False`.
- Expanded `tests/test_memory.py` with FastAPI-level multi-turn context, patient/session isolation, and file-backed SQLite persistence across app restart. Tests use a deterministic local graph; no external LLM/API calls.
- Added `docs/CONVERSATION_MEMORY.md` documenting thread scoping, persistence, no automatic expiry, deletion, backup, privacy, SQLite single-process limitations, and manual UI acceptance steps.
- Focused verification: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_memory.py tests\\test_api.py -q -p no:cacheprovider` — 8 passed. Warnings: Starlette/httpx and Pydantic deprecations. Pytest emitted a Windows temp-directory `PermissionError` during interpreter shutdown after passing.
- Full verification: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider` — 33 passed, 163 warnings, exit code 0. Same known dependency deprecations and post-test Windows temp cleanup warning.
- Remaining constraints: UI manual scenarios are documented but not automated because Streamlit UI runtime/browser interaction is not configured in this environment. No automatic retention or per-patient deletion; establish clinic retention policy before real patient data. SQLite intended for single-process/single-host prototype.


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

### Phase 4 execution entry — 2026-09-29
- Reviewed `data/`: appointment schedule CSV schema and row count only; did not expose/copy patient row data. No verified clinic FAQ facts existed. Created `data/clinic_faq.json` as an empty approved-content store rather than inventing clinic policies.
- Implemented a dedicated FAQ node, FAQ-specific supervisor routing, keyword/question matching against configured JSON, safe unknown-answer fallback, and medical-advice boundary response. Added `tests/test_faq.py`.
- Focused tests: 8 passed. Full suite: 29 passed, 73 warnings, exit code 0. Windows pytest cleanup emitted a shutdown-time permission warning after successful test completion.
- Phase remains in progress until clinic-specific facts are supplied/approved and content update guidance is documented. No commit or push.


### Phase 4 continuation — 2026-09-29
- Added `docs/FAQ_CONTENT_GUIDE.md` with approved-source requirements, JSON schema example, operator update/review steps, and test commands.
- Added synthetic appointment fixture under `tests/fixtures/` (fabricated doctors, dates, availability states, and test-only patient IDs) plus a fixture integrity test. The live `data/doctor_availability.csv` was not edited; fixture README warns not to use it as production data.
- Clinic-specific FAQ facts remain unprovided, so Phase 4 stays in progress until authorized facts are entered and reviewed.

### Phase 5 execution entry — 2026-09-29
- Updated the booking specialist's toolset to include availability lookup and strengthened its operating contract: ask for missing/ambiguous details, request explicit patient confirmation before mutations, report tool outcomes accurately, and never expose patient IDs.
- Added `tests/test_appointment_agent.py` to verify book/cancel/reschedule supervisor routing, all appointment tools exposed to the booking specialist, confirmation/outcome instructions, and worker handoff. Existing tool tests verify persistent mutations and failure paths; existing API tests verify request validation and safe failures.
- Focused command: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_appointment_agent.py tests\\test_tools.py tests\\test_api.py -q -p no:cacheprovider` — 21 passed, 1 Starlette/httpx deprecation warning.
- Full command: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider` — 32 passed, 73 warnings, exit code 0. Warnings include Starlette/httpx and Pydantic deprecations; Windows pytest temporary-directory cleanup raised a shutdown-time `PermissionError` after successful completion.
- Limitation: confirmation is currently an LLM specialist instruction, not a deterministic server-side approval gate. Before production use with real patient records, implement a server-side pending-action confirmation state.
- Phase 5 prototype scope completed; next phase is Phase 6 API/UI conversation-memory verification.


### Phase 7 implementation entry - 2026-09-29
- Added `knowledge_base.py`: deterministic FAQ retrieval over approved JSON content, schema filtering, token coverage scoring, evidence threshold, and fail-closed loading. Integrated it into the existing FAQ node; verified-answer fallback remains.
- Legacy notebook availability queries use structured CSV filtering. Runtime availability and mutations remain centralized in typed `toolkit/toolkits.py` tools; no semantic/vector retrieval is used for live schedule decisions. Live appointment CSV was not modified.
- Added synthetic retrieval tests and `docs/RAG_KNOWLEDGE_BASE.md` describing source boundaries, testing, extension criteria, and limitations.
- Focused tests: 8 passed. Full suite: 37 passed, 163 warnings. Warnings include Starlette/httpx and Pydantic deprecations; Windows pytest temp cleanup PermissionError occurs at shutdown after success.
- Phase 7 remains in progress: clinic FAQ data is empty and no approved clinic corpus or representative evaluation set is available. Current implementation is lexical retrieval, not an embedding/vector database; do not claim production RAG readiness.


### CI failure diagnosis and remediation - 2026-09-29
- Inspected GitHub Actions run 5 job logs: dependency installation failed before pytest because `pywin32==308` was unconditionally included while CI runs on Ubuntu (`No matching distribution found`). The test step was skipped. This was a platform marker defect in the shared requirements file, not a failing application test.
- Added Windows-only environment markers for `pywin32` and `win32_setctime`.
- Improved `.github/workflows/ci.yml`: concurrency cancellation, isolated runner-temp SQLite path, 30-minute timeout, binary-wheel preference, dependency consistency check (`pip check`), compile check, then test suite.
- Local validation: compile check passed; full pytest suite 37 passed (163 existing dependency deprecation warnings). Local venv has no pip module, so `pip check` could not be run locally; workflow will execute it after fresh pip installation.


### Repository and data audit — 2026-09-29
- Audited tracked project structure, current branch/history, roadmap, README, CI workflow, knowledge-base module/docs, data models, synthetic fixture, and data file metadata. Working tree has only the eight previously preserved untracked scratch/isolated test files; no tracked modifications were present before this roadmap update.
- Compared `data/doctor_availability.csv` with `notebook/availability.csv`: both are byte-for-byte identical (SHA-256 `e02843b7e8f39a5486145af933b5e0822cde9d167c229efd59338ca3f09fc9a8`), with 4,280 records and the same five-column schema. Therefore no data replacement/copy is needed: the legacy appointment dataset is already present in the runtime canonical path `data/doctor_availability.csv`; the notebook copy is a duplicate reference artifact.
- Data metadata only (no patient identifiers or row contents displayed): 2,716 available and 1,564 booked rows; 10 doctor names and 7 specialties. Dataset dates are in 2024, so it is historical sample/prototype data, not confirmed current clinic availability. Do not present it as live availability without refresh/approval.
- `tests/fixtures/synthetic_appointments.csv` is a separate 10-row fabricated test fixture. Keep it isolated under tests; never replace the legacy schedule with it or use it as real clinic data. It uses test doctors/specialties and is not a drop-in production dataset.
- `data/clinic_faq.json` is an empty list (7 bytes with UTF-8 BOM); no approved clinic FAQ corpus exists. `knowledge_base.py` implements deterministic lexical FAQ retrieval, not embedding/vector RAG. Appointment availability correctly remains structured CSV/tool retrieval, not semantic search.
- `data_models/models.py` contains one `DateTimeModel`, one `DateModel`, and one `IdentificationNumberModel`; no duplicate class definitions were found in the current file (the earlier screenshot showed an older/different working copy). Do not change it based only on that screenshot.
- README still contains historical/stale statements about no tests, no CI, no memory, and old stateless architecture. Update README as a separate documentation task after verifying current startup/config instructions; it was not changed in this audit.
- CI run reviewed from the supplied GitHub screenshot was cancelled during dependency installation after 2m38s; test execution steps were skipped. The visible Node 20 deprecation and Ubuntu runner migration notices are warnings/not the reported failure cause. A definitive dependency-install error requires opening the expanded install-step logs.
- Next data action: obtain an owner-approved, current clinic schedule and define safe refresh/ownership; preserve this legacy CSV as a versioned prototype/reference copy until source-of-truth and patient-data handling are confirmed. No dataset, secrets, Windows settings, or scratch files were modified.


### Phase 7 continuation — 2026-10-05
- Strengthened `knowledge_base.py` FAQ loading and retrieval: records are normalized, malformed entries fail closed, common stopwords are ignored, optional source metadata is preserved, and low-evidence/empty queries still return no match.
- Updated the FAQ node to include a configured FAQ source ID in grounded answers. Unknown FAQ answers still use explicit no-answer fallback, and appointment availability/mutation workflows remain separate structured CSV tools.
- Updated `README.md`, `docs/RAG_KNOWLEDGE_BASE.md`, and `docs/FAQ_CONTENT_GUIDE.md` to remove stale claims about no tests/CI/memory, document the historical legacy appointment CSV boundary, and clarify that current Phase 7 is lexical retrieval rather than vector/embedding RAG.
- Focused verification: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_knowledge_base.py tests\\test_faq.py -q -p no:cacheprovider --basetemp=.pytest-tmp` — 9 passed. Initial focused run without `--basetemp` hit a Windows temp-directory `PermissionError` before several `tmp_path` fixtures started.
- Additional focused verification: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_tools.py tests\\test_appointment_agent.py -q -p no:cacheprovider --basetemp=.pytest-tmp` — 16 passed; `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_api.py tests\\test_memory.py tests\\test_routing.py -q -p no:cacheprovider --basetemp=.pytest-tmp-api` — 12 passed, 163 dependency deprecation warnings.
- Compile check: `.\\.venv\\Scripts\\python.exe -m compileall -q agent.py main.py toolkit data_models utils knowledge_base.py` — passed.
- Full verification: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-full` — 38 passed, 163 warnings. Warnings are existing Starlette/httpx and LangChain/Pydantic deprecations.
- Remaining Phase 7 constraints: `data/clinic_faq.json` is still empty; no approved clinic corpus, ingestion pipeline, embedding/vector store, or representative retrieval evaluation set exists. Do not claim production RAG readiness.


### Phase 8 implementation work — 2026-10-08
- Added support/handoff.py and support/__init__.py with a local SQLite case queue, case IDs, lifecycle statuses (pending, acknowledged, resolved, cancelled), bounded conversation summaries, sensitive-value redaction, trigger detection, and truthful user-facing status messages.
- Integrated explicit human/complaint escalation into agent.py before LLM routing; unresolved FAQ questions and FAQ retrieval failures now create a local handoff case instead of falsely claiming an answer or human contact. Medical-advice requests remain refused and are escalated when the local queue is available.
- Added HANDOFF_DB_PATH configuration and ignored local handoff database files in Git.
- Added docs/HUMAN_ESCALATION.md documenting triggers, queue lifecycle, privacy minimization, prototype business-hours/SLA policy, and production limitations.
- Added tests/test_handoff.py covering trigger detection, redaction/bounded summaries, case lifecycle, explicit human escalation without an LLM call, unresolved FAQ escalation, retrieval-error escalation, queue failure truthfulness, and invalid status handling. Updated FAQ tests to assert the new escalation contract.
- Focused verification: .venv\\Scripts\\python.exe -m pytest tests\\test_handoff.py tests\\test_knowledge_base.py tests\\test_faq.py tests\\test_routing.py -q -p no:cacheprovider --basetemp=.pytest-tmp-phase8c — 25 passed.
- No real appointment/patient dataset was modified. The generated local handoff database was removed after an early test run created it before the test isolation was corrected.
- Phase 8 prototype scope is complete. Production contact-channel integration, authentication/access control, notifications, retention, and operational ownership remain Phase 10 requirements.

### Phase 7 completion work — 2026-10-08
- Replaced the FAQ runtime retrieval path with semantic embedding retrieval while preserving the deterministic lexical retriever as a baseline.
- Added persistent file-based vector index support in `knowledge_base.py`: normalized embeddings are stored in `embeddings.npy` and normalized FAQ records/source metadata in `metadata.json`.
- Added content fingerprinting so a changed validated FAQ corpus automatically triggers index rebuild; unchanged corpora reuse the persisted index.
- Added configurable `FAQ_EMBEDDING_MODEL`, `FAQ_RAG_INDEX_PATH`, top-k, minimum similarity threshold, and source-ID filtering.
- Added a module CLI for controlled FAQ ingestion/index building: `python -m knowledge_base --source data/clinic_faq.json --index-dir data/faq_index`.
- FAQ node now consumes semantic retrieval and fails closed to the verified-information fallback when evidence or the retrieval service is unavailable; appointment availability/booking/cancellation/rescheduling remain structured tools and are never decided by RAG similarity.
- Added synthetic FAQ and retrieval-evaluation fixtures plus tests for paraphrase retrieval, source metadata, no-answer thresholds, source filtering, index persistence/rebuild, and hit-rate/MRR/no-answer metrics.
- Added `data/faq_index/` to `.gitignore` because the local vector index is generated from the approved FAQ source and should not be committed as runtime state.
- Local venv was missing pip and the already-required `langchain-openai` package. Bootstrapped pip with `ensurepip`, installed `langchain-openai==0.3.9`, then restored the pinned `langchain-core==0.3.45`, `openai==1.66.5`, and `tiktoken==0.8.0` versions from requirements. `pip check` reported no broken requirements.
- Focused verification: `.\.venv\Scripts\python.exe -m pytest tests\test_knowledge_base.py tests\test_faq.py -q -p no:cacheprovider --basetemp=.pytest-tmp-rag4` — 13 passed.
- Compile validation: `.\.venv\Scripts\python.exe -m compileall -q agent.py main.py toolkit data_models utils knowledge_base.py` — passed as part of the validation run.
- Full verification: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-full2` — 42 passed, 163 warnings. Warnings are existing Starlette/httpx and LangChain/Pydantic deprecations.
- `data/clinic_faq.json` remains empty by design. No clinic facts were invented and no appointment/patient dataset was changed.
- Phase 7 implementation is validated, but real-world FAQ activation still depends on clinic-approved FAQ content and content-owner review.

### Phase 9 implementation work — 2026-10-09
- Reworked `streamlit_ui.py` with masked patient-ID input, API-bound input validation, transcript rendering, loading feedback, configurable API URL and timeout, safe text rendering, helpful API/network errors, session reset, and a pending human-handoff status display.
- Added `ui_helpers.py` and unit tests for patient-ID bounds, latest assistant response extraction, and validation of escalation metadata.
- Updated `main.py` to clear previous-turn escalation fields before each invocation and include current handoff status/case metadata in the API response when present.
- Added `tests/test_streamlit_ui.py` using Streamlit AppTest for invalid IDs, successful response rendering, pending escalation feedback, and new-conversation behavior.
- Added `docs/STREAMLIT_UI_ACCEPTANCE.md` for manual browser/responsive/keyboard checks; updated the CI compile step to include the UI and support modules.
- Focused checks: `.venv\\Scripts\\python.exe -m pytest tests\\test_ui_helpers.py tests\\test_api.py tests\\test_handoff.py tests\\test_faq.py tests\\test_knowledge_base.py -q -p no:cacheprovider --basetemp=.pytest-tmp-phase9` — 39 passed, 1 warning. Streamlit AppTest: `tests/test_streamlit_ui.py` — 3 passed.
- Full verification: `.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-phase9-full` — 66 passed, 163 warnings. Compileall passed, `pip check` reported no broken requirements, and `git diff --check` passed (Git only reported line-ending conversion notices).
- Remaining: visual browser/mobile/responsive and keyboard accessibility review were not performed. This phase is implemented for prototype scope but retains that manual acceptance item.


### Phase 10 implementation checkpoint — 2026-10-09
- Hardened `main.py`: `POST /execute` now requires `API_ACCESS_TOKEN` by default and uses constant-time comparison; missing configuration fails with 503, invalid credentials with 401. `ALLOW_UNAUTHENTICATED_LOCAL_DEV=true` is an explicit local-only exception and defaults off.
- Added `/health/live` and `/health/ready`, safe allowlisted request IDs, no-store response headers, and readiness checks for model/security configuration. Shared SQLite checkpointer graph invocations are serialized for the single-process prototype.
- Added bounded OpenAI request timeout/retry configuration and selectable `OPENAI_CHAT_MODEL` in `utils/llms.py`.
- Added `requirements-runtime.txt` and `requirements-test.txt` with a curated pinned supported runtime/test dependency set, avoiding the repository's optional historical ML/CV dependency graph for app deployment. Added `tests/conftest.py` for authorized API calls and `tests/test_llm_config.py` for bounded timeout/retry configuration.
- Added a non-root `Dockerfile`, `.dockerignore`, localhost-only API/UI `docker-compose.yml`, deploy-only FAQ template, runtime-data exclusion from Git, and security configuration in `.env.example`. Historical schedule data is not copied into the image; deployment must provision an authorized current schedule separately.
- Updated CI to install the runtime/test manifests, run `pip check`, compile app/UI/support modules, run pytest, and build a container image. Updated `docs/CI_CD.md`, added `docs/PRODUCTION_READINESS.md`, and updated README instructions/limitations.
- Full validation: `.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-phase10-full` — 83 passed. `python -m compileall -q agent.py main.py streamlit_ui.py ui_helpers.py toolkit data_models utils knowledge_base.py support` passed. `pip check` — No broken requirements found. `docker compose config --quiet` passed using non-secret placeholder values. `git diff --check` passed; Git emitted only expected LF/CRLF working-copy notices.
- Local `docker build` was attempted but failed because the Docker Desktop Linux engine pipe was unavailable. The actual image build remains unverified locally; CI now includes a hosted image-build step and must pass after this push.
- No `data/doctor_availability.csv`, real patient dataset, `.env`, `scratch*`, or `isolated_test*` file was staged or modified. No secret/token values were committed.
- Phase 10 remains in progress (approximately 65%). This is not ready for real clinic data: remaining items include end-user authentication/authorization, rate limiting/TLS, policy-based retention/deletion/encryption and access auditing, managed production persistence/transactional booking data, real staffed human escalation, backup/recovery, security/load testing, deployment/rollback, plus the approved FAQ and current appointment schedule. Phase 9 still needs manual browser/responsive review.


### Follow-up validation checkpoint — 2026-10-09
- Re-ran the full test suite on the current branch head: `83 passed in 3.84s`. Re-ran `compileall`, `pip check` (`No broken requirements found`), `docker compose config --quiet`, and `git diff --check`; all passed.
- A loopback-only Streamlit smoke server returned HTTP 200 for `/`, `/_stcore/host-config`, and `/_stcore/health`. Automated Streamlit AppTest coverage passes as part of the full suite. However, a headless Chrome capture at a 390px viewport remained on the loading skeleton, so manual browser/responsive/keyboard acceptance is **not** marked complete.
- Attempted to launch the installed user-scope Docker Desktop application to validate the image build. Its Docker engine remained unavailable after 90 seconds, so the container image build remains unverified. The temporary Streamlit test processes and the Docker Desktop processes started for this attempt were stopped; no project services are intended to remain running.
- Rechecked GitHub Actions for `af7ff52c031f2dc03ccc7bb8e7c3b13243514318`: no workflow run and no check runs/status checks exist for that SHA. The latest recorded Actions run is still run #10 from 2026-09-29, cancelled. Hosted CI is therefore pending, not green.
- No approved clinic FAQ, authorized current appointment schedule, staffed escalation channel, production identity provider, deployment target, or retention/security policy was supplied. Those business/environment requirements remain release blockers rather than being filled with invented clinic facts or secrets. No real appointment/patient data, `.env`, or scratch/isolated files were changed or staged.


### Phase 1 — isolated synthetic demo data — 2026-10-09
- Added `deployment/demo_data/clinic_faq.json` with six fictional FAQ entries; every answer explicitly begins with `DEMO ONLY` and its source metadata states that the content is not clinic-approved.
- Added `deployment/demo_data/doctor_availability.csv` with 18 synthetic slots using only doctor/specialization values accepted by the current appointment tool schemas and test-only patient IDs (`9100001`–`9100005`). Dates are frozen demo values, not live availability.
- Added `deployment/prepare_demo_data.ps1`. It requires the exact `DEMO-ONLY` confirmation and refuses to overwrite any pre-existing `runtime-data/` directory. Since none existed, the script was run with the confirmation and copied the sample files into ignored local `runtime-data/` for a disposable Compose demo.
- Made the FAQ source configurable with `CLINIC_FAQ_PATH` (default remains the existing `data/clinic_faq.json`). Compose now uses `/app/runtime-data/clinic_faq.json` explicitly, without mounting over the canonical source file.
- Added `tests/test_demo_data.py` for FAQ warning labels, appointment schema/state validity, and isolated fake booking/cancellation. Added an FAQ-path override test and updated README, environment example, and production-readiness instructions.
- Focused verification: `tests/test_demo_data.py tests/test_faq.py tests/test_tools.py` — 22 passed. Full suite: 87 passed in 3.15s. `compileall`, `pip check`, Compose configuration parsing, PowerShell script parser, and `git diff --check` all passed.
- Data-integrity check: original `data/doctor_availability.csv` still has SHA-256 `e02843b7e8f39a5486145af933b5e0822cde9d167c229efd59338ca3f09fc9a8`; `data/clinic_faq.json` remains empty. The fake booking/cancellation test operated only on a temporary copy. No `.env` or scratch/isolated file was modified or staged.
- Docker image build remains unverified because Docker Desktop's engine is still unavailable. The fake data kit does not make the project production-ready and must not be used with real clinic workflows.


### Phase 10 continuation — deterministic appointment mutation confirmation — 2026-10-09
- Removed direct book/cancel/reschedule tools from the booking agent. It now receives read-only availability tools and `prepare_appointment_change`, which validates the exact doctor/date/action, stores a pending proposal, and explicitly states that no schedule mutation has been performed.
- Added `support/pending_actions.py`: SQLite-backed pending actions scoped to the hashed patient/session thread, 15-minute expiry, exact payload validation, one pending action per thread, an atomic one-time claim before execution, and terminal states for executed/cancelled/failed/expired actions. Confirmation is intentionally narrow: standalone `YES`/`NO` and explicit supported Arabic yes/no variants only. Mixed or unrelated messages are ambiguous and do not authorize mutation.
- Updated `main.py` so the API—not the LLM—claims and executes the stored payload after confirmation. It does not take appointment parameters from the confirmation message or rerun the agent to decide the mutation. Confirmation turns are added to the current LangGraph checkpoint. Added `PENDING_ACTION_DB_PATH` for isolated local/demo persistence and Compose, and ignored generated database/test-temp artifacts in Git.
- Updated `README.md`, `docs/PRODUCTION_READINESS.md`, and Phase 5/10 roadmap descriptions. The gate is a deterministic prototype safeguard, not patient authentication or a complete audit/authorization system.
- Added `tests/test_pending_actions.py` for expiry, session isolation, duplicate prevention, exact-confirmation parsing, invalid payloads, and prepare-only behavior. Added API tests for successful stored-action execution, ambiguous confirmation rejection, patient/session isolation, declined requests, and a full API-to-appointment-tool booking against a temporary copy of the synthetic demo schedule.
- Focused verification: `tests/test_pending_actions.py tests/test_appointment_agent.py tests/test_api.py tests/test_tools.py` — 55 passed. Full suite: `python -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-approval-full-final` — 115 passed in 3.53s.
- Additional verification: `compileall` passed; `pip check` reported `No broken requirements found`; `docker compose config --quiet` passed with non-secret placeholder values; `git diff --check` passed (only Git LF/CRLF working-copy warnings). Confirmed `data/doctor_availability.csv` SHA-256 is unchanged (`e02843b7e8f39a5486145af933b5e0822cde9d167c229efd59338ca3f09fc9a8`) and `data/clinic_faq.json` remains `[]`. Synthetic integration changed only a temporary CSV copy.
- Previously dispatched hosted CI run #12 on commit `8a8ad90` succeeded, including its Docker image build. This new phase must be pushed and its own workflow run checked separately. Remaining release blockers: real patient identity/authentication and role authorization, transactional operational data, clinic-approved FAQ/current schedule, real staffed handoff, production privacy/security controls, and manual browser/accessibility acceptance.


### Phase 10 continuation — local image and hosted CI verified — 2026-10-09
- Current branch head before this documentation update: `fd401022cb0bfc2a1f35e2f71dd4dfec8c1a1163` (`feat: enforce server-side appointment confirmation`), matching `origin/ci/fix-github-actions`.
- Full local test suite on that commit: `115 passed in 3.29s`.
- Docker Desktop Linux engine became available. `docker build --pull -t clinic-ai-customer-service:fd40102 .` completed successfully. Image ID: `sha256:02febee859bfdcd49e1d865f57eb02619f36c327de2e3388f552291fc6fac55b`; image runs as the non-root user `app` and is approximately 208 MB.
- Ran an isolated container import smoke test using the built image: imports for FastAPI, Streamlit, LangGraph, LangChain OpenAI integration, `main`, `ui_helpers`, and `support.pending_actions` passed. Reported versions: FastAPI 0.115.8 and Streamlit 1.42.2.
- Verified GitHub Actions run #13 for commit `fd401022cb0bfc2a1f35e2f71dd4dfec8c1a1163`: success. Every job step passed, including dependency installation, `pip check`, compileall, the full test suite, and the production container build. Run: https://github.com/moamedmer68-commits/clinic-ai-customer-service/actions/runs/37967555426
- The current `runtime-data/` directory contains only the two documented synthetic demo input files before runtime testing. No real schedule or patient records were used. The repository's real historical appointment CSV and empty canonical FAQ source remain unchanged; no `.env` or scratch/isolated files were modified or staged.
- Still not marked complete: full Compose API+UI end-to-end smoke with a usable model credential, real-browser mobile/keyboard acceptance, clinic-approved FAQ, an authorized current schedule, a staffed human handoff channel, patient identity/role authorization, production privacy/security controls, managed transactional persistence, backup/restore, load/security testing, and deployment/rollback. Successful CI/container build proves packaging and automated checks, not production-clinic readiness.


### Container and hosted-CI verification — 2026-10-09
- GitHub Actions run #13 for `fd40102` completed successfully: https://github.com/moamedmer68-commits/clinic-ai-customer-service/actions/runs/37967555426. The run includes the current test/build workflow; the next documentation checkpoint will trigger a fresh run for its own SHA.
- Re-ran the current full local test suite: `115 passed in 3.50s` (pytest returned exit code 0). Pytest emitted a Windows `PermissionError` from its temporary-directory cleanup callback after reporting all tests passed; this is a local temp-cleanup warning, not a test failure.
- Docker Desktop became available. `docker build -t clinic-ai-customer-service:latest .` completed successfully and produced a 208 MB image.
- `docker compose up -d --build` successfully built the Compose API/UI images and started both services using only the isolated `runtime-data/` demo fixtures and placeholder, non-secret environment values. API container reached `healthy`; `/health/live`, `/health/ready`, and the Streamlit `/` returned HTTP 200; unauthenticated `POST /execute` returned HTTP 401 as intended. `docker compose config --quiet` passed.
- Stopped the local Compose stack with `docker compose down`; verified no containers from this Compose project remained running. Demo fixtures remain in ignored `runtime-data/` for the explicitly prepared local demo. The committed source schedule SHA-256 remains `e02843b7e8f39a5486145af933b5e0822cde9d167c229efd59338ca3f09fc9a8` (unchanged).
- Remaining uncompleted items are environment/business acceptance: browser keyboard/accessibility/manual responsive review, real clinic-approved FAQ and current schedule, staffed human handoff, patient identity/role authorization, production transactional data and audit/retention/security controls, backups/restore, load/security testing, and an approved deployment/TLS/rollback plan. Passing local and hosted CI plus Compose smoke tests does not make this prototype safe for real patient data.
- No `.env`, real patient/appointment data, or scratch/isolated files were changed or staged.


### Development-plan checkpoint — 2026-10-15
- Added DEVELOPMENT_PLAN.md at the repository root to capture the newly agreed product direction, phase sequence, acceptance criteria, and progress log. ROADMAP.md remains the repository-wide implementation/verification history; DEVELOPMENT_PLAN.md is the execution guide for the next development cycle.
- Confirmed scope decisions: keep OpenAI unchanged; support new-patient registration inside the application; generate a unique Patient ID only after the agreed identity-verification flow succeeds; target production readiness; support Arabic and English.
- Phase 0 runtime diagnosis: local API /health/ready returned HTTP 200 after restart and focused API/memory tests passed (19 passed). A direct OpenAI model invocation returned HTTP 429 with insufficient_quota / credit_balance_exhausted. This is the immediate end-to-end runtime blocker; a ready endpoint does not prove the LLM account has usable quota.
- Phase 0 remains in progress until usable OpenAI quota is available and a genuine Streamlit-to-API-to-agent chat request succeeds, or a reproducible remaining failure is captured.
- Git review: local HEAD matched origin/ci/fix-github-actions at ddd8b5854cb7084f26cf9ed83b11fed8f018e5f9. No unresolved merge-conflict paths were reported. Existing local working-tree paths tests/test_tools.py, toolkit/toolkits.py, isolated_test*.py, scratch.py and scratch2.py are to be preserved and must not be reset/deleted/staged without re-inspection.
- No provider change, code changes, commit, or push was performed for this checkpoint.


### Phase 7 verification entry - 2026-10-18
- Reviewed the Phase 7 checklist and its source-of-truth boundary before acting. Existing semantic RAG, strict FAQ preflight, persistent index, source metadata, content fingerprinting, safe no-answer behavior, and synthetic evaluation are implemented.
- Focused verification: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_knowledge_base.py tests\\test_faq.py tests\\test_routing.py tests\\test_demo_data.py tests\\test_synthetic_fixture.py -q -p no:cacheprovider` - 25 passed in 4.88s.
- Canonical source check: `.\\.venv\\Scripts\\python.exe -m knowledge_base --source data\\clinic_faq.json --index-dir data\\faq_index` exited 2 with `FAQ source is empty; add clinic-approved entries before building the index`. This is expected and safe: the canonical corpus is intentionally empty, and no clinic-approved facts were provided.
- `deployment/demo_data/clinic_faq.json` contains six explicitly labelled fake/demo answers and is not an approved substitute. It remains isolated; no synthetic or historical content was copied into the canonical FAQ source, and no vector index was built from unapproved facts.
- No application code or user working files were changed in this session. Existing local modifications and untracked scratch files were preserved. No commit or push performed.
- Remaining Phase 7 blocker: clinic owner must provide/review FAQ facts and confirm owner, source, review date, and update process. Then ingest the approved corpus, add reviewed bilingual paraphrase/unsupported-query evaluation cases, and run retrieval relevance checks using a working embedding API quota. Real-clinic activation remains blocked until that evidence exists.


### Phase 7 synthetic bilingual dataset update - 2026-10-18
- Added/expanded `deployment/demo_data/clinic_faq.json` to 26 fabricated FAQ records: 13 English and 13 Arabic records across 13 topics. Every answer is explicitly marked as demo/fake and its source metadata says it is not clinic-approved.
- Added `tests/fixtures/synthetic_faq_retrieval_eval_bilingual.json` with 32 synthetic evaluation queries: 26 expected supported-topic matches and 6 intentionally unsupported questions.
- Updated `tests/test_demo_data.py` to verify record count, unique IDs, language coverage, fake-data warnings, and evaluation fixture shape. Updated `deployment/demo_data/README.md` to describe the expanded dataset.
- Verification: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_demo_data.py tests\\test_knowledge_base.py tests\\test_faq.py tests\\test_routing.py tests\\test_synthetic_fixture.py -q -p no:cacheprovider` - 26 passed in 4.05s.
- The canonical `data/clinic_faq.json` remains unchanged and empty. The synthetic FAQ is only under the demo-data directory and is not clinic-approved. No OpenAI embeddings or production index were generated because the recorded OpenAI quota issue may still block external embedding calls; no claim is made that semantic retrieval accuracy on the bilingual fixture has been measured yet.
- Preserved pre-existing local changes in `tests/test_tools.py`, `toolkit/toolkits.py`, `.vscode/`, `isolated_test*.py`, and `scratch*.py`. No commit or push performed.


### Phase 9 frontend polish — 2026-10-18
- Reviewed the Phase 9 status and `docs/STREAMLIT_UI_ACCEPTANCE.md` before editing. Reworked `streamlit_ui.py` into a responsive CareDesk-style layout: custom visual hierarchy, teal/navy theme, hero panel, compact service/language/privacy cards, improved chat bubbles and mobile spacing, and clearer prototype/privacy/escalation notices.
- Added an English/Arabic interface selector with translated headings, patient-ID instructions, error states, loading message, and demo safety footer. Kept patient ID masked and validation before API calls; user/assistant messages continue to render with raw HTML disabled. Kept the new-conversation button as the first button for existing UI tests and preserved the API request contract.
- Added an AppTest for switching the UI to Arabic. Focused verification: `python -m pytest tests\\test_streamlit_ui.py tests\\test_ui_helpers.py -q -p no:cacheprovider` — 16 passed. Full suite before the new language-toggle test: 119 passed in 7.10s; rerun the full suite after the final test addition. `compileall` and `git diff --check` passed (only line-ending notices).
- Not completed: manual browser screenshots at desktop/mobile widths, keyboard-only navigation, contrast/accessibility audit, and live API/model interaction. Automated AppTest does not prove these visual acceptance criteria. The existing OpenAI quota issue may block genuine model interaction.
- No secrets changed, no commit/push performed, and pre-existing user modifications/untracked scratch files preserved.


### Phase 10 verification checkpoint - 2026-10-18
- Reviewed `docs/DEVELOPMENT_PLAN.md`, `docs/PRODUCTION_READINESS.md`, and `docs/CI_CD.md` before verification. Scope remains production-readiness evidence and release gates; this checkpoint does not claim real-clinic readiness.
- Current branch commit `71e76568fd4f4eb68d248670a0827d5f9d316d95` passed GitHub Actions run #18: dependency install/checks, compile, full tests, and container image build. Run: https://github.com/moamedmer68-commits/clinic-ai-customer-service/actions/runs/39129199285
- Local full test suite: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-phase10-final` - 120 passed in 7.74s.
- Local compile check passed for app, UI, toolkit, data models, utilities, knowledge base, and support modules. `pip check` reported `No broken requirements found`; `docker compose config --quiet` passed; `git diff --check` passed.
- A fresh local Compose/container runtime check could not be repeated because Docker Desktop's Linux engine pipe was unavailable. The hosted CI image build passed for this commit; no claim is made that local containers were started in this checkpoint.
- Current GitHub Actions run confirms CI/build for the pushed commit only; it does not complete manual browser/mobile/keyboard accessibility acceptance, a genuine model call (OpenAI quota issue remains documented), or production operational approvals.
- Phase 10 remains **in progress**. Release blockers still include clinic-approved FAQ and current schedule, end-user authentication/authorization, rate limiting/TLS/managed secrets, retention/deletion/audit/encryption policies, production transactional persistence, staffed human escalation, backup/restore rehearsal, security/load tests, deployment/rollback and manual UI acceptance. These require clinic/environment decisions and evidence, not fabricated defaults.
- Existing user changes in `tests/test_tools.py`, `toolkit/toolkits.py`, `.vscode/`, `isolated_test*.py`, and `scratch*.py` were preserved. No secrets or patient data were staged or changed; no commit/push performed for this documentation checkpoint.


### Repository organization checkpoint — 2026-10-18
- Moved the eight local exploratory scripts from the repository root to `dev/experiments/` without changing their contents and added a folder README. They remain local/untracked and were not staged.
- Kept production entrypoints and modules in the root because Dockerfile COPY commands, tests, and current commands import them by those paths. A wider package-layout refactor is intentionally deferred.
- Verification after organization: full suite 120 passed in 7.45s; compile check, `docker compose config --quiet`, and `git diff --check` passed. Existing user changes were preserved; no commit or push performed.


### Phase 0 runtime recheck — 2026-10-18
- Rebuilt and started the local Compose stack using `docker compose up -d --build`; API and UI images built successfully.
- Verified API `/health/live` = HTTP 200, API `/health/ready` = HTTP 200, and Streamlit `/` = HTTP 200 after startup; API container reached Docker `healthy`.
- This is runtime/endpoint verification only, not a successful end-to-end LLM chat. The known direct OpenAI error remains HTTP 429 `insufficient_quota` / `credit_balance_exhausted`; real UI-to-agent smoke acceptance is still blocked until usable OpenAI API quota is restored.
- No provider change, application-code change, secret read/change, commit, push, or merge performed. Existing working-tree changes preserved.


### Phase 0 end-to-end blocker reproduced — 2026-10-18
- Sent a synthetic request from the UI container to `POST /execute` with the configured service credential (secret value not printed): HTTP 500, request ID `d96182df-a964-458b-94cb-a05ce2445b12`, safe error `agent_execution_failed`.
- Sanitized API logs correlate that request with repeated OpenAI Chat Completions HTTP 429 and `insufficient_quota` / `credit_balance_exhausted` (“no credits remaining”). Thus UI/API transport is working; the genuine agent response is blocked by OpenAI API billing/quota.
- Phase 0 remains blocked pending restored quota and a repeated successful UI-to-agent smoke test. Compose containers remain running. Synthetic test only; no real patient data, secrets displayed, app code changed, commit or push.


### Patient account security work — 2026-10-18
- Added SQLAlchemy patient account/session models, manual-review registration, staff approval, post-approval unique 8-digit Patient ID generation, password hashing, expiring opaque bearer sessions, login/me/logout endpoints, and patient-session enforcement for POST /execute when PATIENT_AUTH_REQUIRED=true.
- Added PostgreSQL Compose service/volume and database configuration/dependencies. Added focused account/auth tests.
- Staff review currently relies on a separate shared STAFF_REVIEW_TOKEN; individual staff identities/RBAC and production safeguards remain open. Existing Streamlit UI has not yet been integrated with login/registration, so Phase 3 is required before end-user chat works with patient auth enabled.
- This is an implementation checkpoint only, not production readiness. No commit/push; existing user changes preserved.


### Phase 3 execution entry - patient onboarding - 2026-10-20
- Created the branch feat/phase-3-patient-onboarding before making Phase 3 UI changes. The previous local Phase 2 verification edits were preserved.
- Updated streamlit_ui.py to provide English/Arabic registration and sign-in forms against the existing patient API routes. New registrations remain pending staff identity review; the UI does not fabricate or issue a Patient ID.
- Chat is now gated on an approved login: the UI reads the Patient ID from the API-issued patient profile, sends the bearer token with /execute, and supports logout through /patients/logout. Removed manual Patient ID entry from the normal user journey.
- Added AppTest coverage for onboarding, registration request fields, login token/profile handling, authenticated chat payload, and language selection.
- Focused tests: 26 passed (tests/test_streamlit_ui.py tests/test_ui_helpers.py tests/test_patient_accounts.py). Final full suite after auth-expiry handling: 130 passed in 11.25s. Compileall, pip check, Compose config validation, and git diff --check passed. Docker Compose UI image build was attempted but could not connect because the Docker Desktop Linux engine pipe was unavailable.
- Manual desktop/mobile, keyboard/accessibility, and genuine API/model acceptance remain open. The known OpenAI insufficient-quota issue blocks confirmation of a real agent response. Shared staff-review token/RBAC and production security controls remain release blockers.
- No commit/push, secret access, or real patient data use.

### Phase 4 workflow safety revalidation - 2026-10-20
- Started work on `feat/phase-4-agent-workflow-safety`, preserving the existing uncommitted Phase 2/3 edits.
- Existing automated coverage for routing, appointment booking/cancellation/rescheduling intent, FAQ unknown-answer fallback, pending-action exact confirmation/decline/expiry/session scoping, human handoff status, and patient isolation was revalidated.
- Focused suite: 66 passed in 8.75s. Full suite: 130 passed in 11.13s.
- No implementation change was made because this pass found no failing automated regression requiring a code change. Phase 4 remains in progress: live bilingual model acceptance is blocked by OpenAI API 429 insufficient_quota; clinic-approved knowledge/current availability and a staffed human escalation destination are still absent. Automated tests do not prove production readiness.
- No commit or push performed; no secrets or real patient data used.

### Phase 5 data readiness - 2026-10-20
- Switched to `feat/phase-5-approved-clinic-data`; preserved existing working-tree changes and did not commit/push.
- Stopped the temporary local UI/API demo processes and removed the temporary demo-auth bypass from the UI source. Normal patient sign-in and API patient-session enforcement are restored in source; no `.env` values were modified.
- Confirmed `data/clinic_faq.json` is empty. Existing appointment/demo fixtures are synthetic/historical, not an approved live schedule. No fabricated clinic facts or live availability were added.
- Strict FAQ validation, FAQ behavior and synthetic-data safety tests: 21 passed. Full suite: 130 passed in 11.38s.
- Phase 5 remains blocked for real-clinic use until a clinic owner supplies/reviews current FAQ and schedule data and documents source, timezone, ownership and update/expiry rules. Docker Desktop engine was unavailable; no container runtime validation was possible.

### Phase 6 handoff lifecycle hardening - 2026-10-20
- Started branch `feat/phase-6-handoff-lifecycle`, preserving working-tree edits. Not yet pushed: Phase 5 remains blocked on clinic-owned data, and `streamlit_ui.py` needs encoding repair before a safe publish.
- Added a strict SQLite handoff status transition graph and transactional status updates; terminal resolved/cancelled cases cannot be reopened, unknown case IDs return false, and invalid transitions raise a validation error.
- Handoff tests: 10 passed. Full suite: 132 passed in 12.30s.
- External staffed notification, authenticated staff case-management, and approved retention/deletion policy remain open; local queue is not represented as a live human handoff.

### Phase 7 initial security lifecycle - 2026-10-20
- Added a staff-authorized account deactivation endpoint. It marks the patient account deactivated and revokes all active sessions transactionally; unauthenticated staff requests are denied and missing accounts return 404.
- Account tests: 10 passed; full suite: 134 passed in 15.48s.
- Phase 7 remains in progress: production migrations, staff RBAC, rate limiting, account recovery, audit/privacy lifecycle, HTTPS/secret rotation, backup/restore and load/security tests remain open. Docker runtime check unavailable.


### Phase 7/8 continuation — security controls and verification — 2026-10-23
- Added security_controls.py with persistent database-backed login throttling (five invalid-credential attempts per normalized email identifier triggers a 15-minute lock) and minimal security audit events. Audit rows store event type, request ID, timestamp, and optional internal account ID; they deliberately exclude email, phone, Patient ID, password, tokens, and request bodies.
- Wired the controls into the patient login flow and staff account approval/deactivation routes. Successful login clears the associated failed-attempt record; locked attempts return HTTP 429.
- Added regression tests for lockout after five failures, HTTP 429 behavior, audit-event minimization, and clearing failures after successful login.
- Updated Dockerfile to include the new module and CI compile step to compile it.
- Verification on the current working tree: patient account tests — 12 passed; full suite — 136 passed in 18.82s; compileall passed; pip check reported no broken requirements; docker compose config --quiet passed; git diff --check passed (only LF/CRLF working-copy warning).
- Phase 8 container build attempted via docker compose build but could not run because Docker Desktop's Linux engine pipe is unavailable (dockerDesktopLinuxEngine not found). No hosted CI run was dispatched because that requires pushing, and no push/commit was authorized. No deployment was attempted.
- Phase 7 remains IN PROGRESS: login throttling is per email identifier and does not replace edge/IP rate limits; staff access still uses a shared token rather than individual identities/RBAC; production database migrations, recovery, retention/deletion policy, TLS/secret rotation, backup/restore, and load/security review remain open.
- Phase 8 remains IN PROGRESS: local tests/config checks pass, but image build, PostgreSQL container/runtime validation, manual bilingual/responsive/accessibility acceptance, live OpenAI-backed UI-to-agent smoke test (previously blocked by OpenAI quota), staging, restore/rollback rehearsal, and release approval remain outstanding.
- No commit, push, reset, or deletion performed. No secrets or real patient data were read or used.


### Phase 9/10 execution entry — 2026-10-23
- Revalidated Phase 9 frontend/UI and Phase 10 production-readiness checks against the roadmap and current source tree. Existing UI implementation already includes bilingual registration/sign-in, chat transcript, session controls, input validation, loading/error feedback and handoff status; no unrelated UI rewrite was warranted.
- Focused verification command: `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_ui_helpers.py tests\\test_streamlit_ui.py tests\\test_api.py tests\\test_handoff.py -q -p no:cacheprovider --basetemp=.pytest-tmp-phase9-10-focused` — 44 passed in 3.31s.
- Full verification command: `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-phase9-10-full` — 136 passed in 15.18s. `compileall` passed; `pip check` reported no broken requirements; `docker compose config --quiet` passed; `git diff --check` passed with LF/CRLF working-copy notices.
- Docker Desktop Linux engine was unavailable (`dockerDesktopLinuxEngine` pipe missing), so a new image build or Compose runtime smoke test could not be completed. Hosted CI was not triggered because the working tree remains uncommitted/unpushed.
- Added `docs/PROJECT_COMPLETION_REPORT_2026-10-23.md` with the phase-by-phase implementation summary, architecture, verification evidence and production blockers. Updated README's stale test count from 130 to 136.
- Phase 9 remains in progress until manual browser/mobile/responsive/keyboard accessibility and real API/model acceptance are performed. Phase 10 remains in progress pending staff RBAC, edge/IP rate limiting, account recovery, retention/privacy controls, managed transactional persistence, approved clinic FAQ/current schedule, staffed escalation, Docker/runtime validation, backup/restore, security/load testing, staging and rollback approval.
- No commit, push, deployment, reset, or deletion performed. No secrets or real patient data were accessed.


## 2026-10-24 development-plan checkpoint
- Rechecked local service readiness: FastAPI /health/ready returned HTTP 200 and Streamlit / returned HTTP 200 after starting both services locally.
- The latest full automated suite on the working tree passed 136 tests in 16.96s; Python compile checks and git diff --check passed. These checks do not prove a successful live OpenAI chat or production readiness.
- Phase 0 remains blocked for acceptance because the last documented OpenAI model invocation returned 429 insufficient_quota / credit_balance_exhausted. A successful UI-to-agent model response was not demonstrated in this checkpoint.
- Prepared docs/REGISTRATION_IDENTITY_DESIGN.md for Phase 1, covering minimum-data registration, staff review/email/SMS verification options, acceptance criteria, and decisions needed from the clinic owner. No verification provider or identity method was invented and no new identity-verification code was added before approval.
- Phase 2/3 existing account and bilingual UI implementation remains in progress; Phase 4 still needs live Arabic/English workflow acceptance; Phase 5 is blocked on clinic-approved FAQ and current authorized schedule; Phase 6 needs staffed handoff and retention policy; Phase 7 needs named staff RBAC, production database migrations, rate limiting, privacy/security/backup controls; Phase 8 needs container/runtime, manual UI, staging, recovery/rollback, and release approval evidence.
- No secrets or real patient data accessed. No commit, push, reset, or deletion performed.


### 2026-10-24 — Codebase refactoring audit
- Began the requested codebase cleanup with a repository/architecture audit documented in `docs/REFACTORING_AUDIT_2026-10-24.md`. Reviewed README, runtime/test dependency manifests, Dockerfile, roadmap/development plan, API, agent, UI, account/session, RAG, security, tool, support, data-model, and utility modules.
- Updated README onboarding/API guidance to match the current approved direct-registration decision (no identity verification or staff approval for new registrations). Existing staff endpoints are described as legacy; no migration or deletion of legacy routes/data was performed.
- Baseline full suite: 10 failed, 126 passed in 14.81s. All 10 failures are existing account tests asserting the former HTTP 202 pending-review contract, while the working-tree API returns HTTP 201 and an authenticated session. This mismatch is recorded and must be resolved with behavior-specific tests; no failures were suppressed.
- Ruff is not installed in the current virtual environment, so no Ruff result is claimed and no dependency was added. The large historical `requirements.txt` was not pruned because `setup.py` consumes it as `install_requires` and it may serve notebooks/experiments or downstream installs. Runtime dependencies remain separately pinned in `requirements-runtime.txt`.
- No broad module moves or agent/prompt changes were made because Docker COPY paths and tests rely on the existing module layout, and the audit did not establish safe redundant agent layers. Arabic UI encoding repair is deferred to a focused change.
- No commit, push, reset, deletion, secret access, or real-patient-data use. Full refactor is not complete; next priority is reconciling registration behavior and account tests, then rerunning validation.
