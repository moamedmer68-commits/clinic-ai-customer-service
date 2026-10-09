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
| 4 | FAQ Agent | In progress — grounded FAQ logic/tests and content guide exist; clinic-approved facts remain missing | 83% |
| 5 | Appointment Agent Integration | Completed for prototype — specialist tools, confirmation instructions, routing/integration and mutation tests verified | 100% |
| 6 | Conversation Memory | Completed for prototype — API multi-turn/restart persistence, isolation, Streamlit controls, operations guidance verified | 100% |
| 7 | RAG Knowledge Base | Blocked for real-world activation — semantic RAG implementation, persistent vector index, ingestion, source tracking, and synthetic evaluation verified; clinic-approved corpus remains external dependency | 95% |
| 8 | Support & Human Escalation | Completed for local-queue prototype — deterministic triggers, privacy-minimized handoff records, status tracking, truthful responses, and tests verified | 100% |
| 9 | Frontend Chat Experience | Implemented and AppTest verified — transcript, session controls, masked ID validation, service errors, and escalation feedback; manual browser/responsive review remains | 90% |
| 10 | Production Readiness | In progress — CI checks and local environment exist; deployment/security/operations requirements remain | 25% |

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
**Goal:** Answer clinic service questions from approved, maintained clinic information.
**Data review (2026-09-29):** `data/` contains `doctor_availability.csv` (columns: `date_slot`, `specialization`, `doctor_name`, `is_available`, `patient_to_attend`; 4,280 data rows) and no authoritative clinic FAQ facts. The appointment CSV is used by appointment availability/booking workflows and is not treated as a source for clinic hours, address, fees, insurance, or policies. No patient row values were copied into FAQ content.
**Implemented:** Dedicated `faq_node` receives FAQ intent; it reads approved entries from `data/clinic_faq.json`, matches question/keyword terms, returns configured answer text, and safely defers unknown questions. Medical-advice terms trigger a boundary response. FAQ routing is distinct from availability routing. The JSON file is currently an empty list because clinic facts have not been provided/verified.
**Tasks:**
- [x] Define FAQ source format and keep it separate from appointment data.
- [x] Implement dedicated FAQ capability with boundaries and fallback for absent information.
- [x] Ground answers in configured content; do not invent clinic policies or provide unsupported medical advice.
- [x] Test known answers, paraphrases, missing answers, medical-advice boundary, and supervisor routing.
- [ ] Populate and verify authoritative FAQ content (hours, location, services, policies, preparation, payment/insurance if applicable).
- [ ] Document the content update process for clinic operators.
**Acceptance criteria:** answers supported by configured source content; unknown answers transparently deferred; routing/tests pass; clinic content approved. The final content approval criterion remains open.
**Verification:** `python -m pytest tests/test_faq.py tests/test_routing.py -q -p no:cacheprovider` — 8 passed. Full `python -m pytest -q -p no:cacheprovider` — 29 passed, 73 warnings. A pytest temporary-directory cleanup emitted a Windows `PermissionError` during interpreter shutdown after tests; pytest exit code was 0. Existing Starlette/httpx and Pydantic deprecation warnings remain.
## Phase 5 — Appointment Agent Integration
**Goal:** Deliver complete appointment workflows through the agent/API using Phase 1 integrity guarantees.
**Implemented/evidence observed:** lookup, booking, cancellation, and rescheduling tools exist in toolkit/toolkits.py; booking agent/node exists.
**Implemented:** The booking specialist now has availability lookup plus book/cancel/reschedule tools. Its instructions require exact details, clarification before tool use, explicit confirmation before mutation, faithful reporting of tool outcomes, and no disclosure of patient IDs. Existing tools enforce patient-ID matching for cancellation/rescheduling, prevent double booking, return explicit unavailable/missing/data-error outcomes, and preserve state on failed atomic writes. Supervisor clarification prevents incomplete appointment requests from reaching the specialist.
**Verification:** Added `tests/test_appointment_agent.py` for booking/cancel/reschedule routing, specialist tool availability, confirmation/outcome instructions, and worker response handoff. Existing `tests/test_tools.py` covers booking, cancellation, rescheduling, unavailable/mismatched appointments, persistence, concurrency, and failed writes. API contract/error tests remain in `tests/test_api.py`.
**Acceptance criteria:** supported appointment intents route to the booking specialist; tool contracts validate required date/ID inputs; mutation results are explicit and state integrity is covered by tests; API errors remain safe.
**Operational limitation:** confirmation is enforced as an explicit specialist instruction to the LLM, not as a separate deterministic server-side approval token. Production-grade guaranteed confirmation should move to a server-side pending-action/approval state before enabling real patient mutations.
**Current status:** Completed for the current agent prototype; deterministic server-side confirmation remains a production-hardening item (Phase 10).

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
