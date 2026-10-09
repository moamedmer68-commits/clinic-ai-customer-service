# Master Project Audit & Implementation Roadmap

Source: original repository audit and roadmap approved for controlled implementation.

This file is the persistent master reference for coding agents. It preserves the original audit decisions and 10-phase roadmap. Agents must continue from the current repository state rather than restart the project.

## Project Context

Existing Doctor Appointment Multi-Agent System using Python, LangGraph, LangChain, OpenAI Chat Models, FastAPI, Streamlit, Pandas, CSV-based appointment data, and Pydantic.

Existing components identified by the audit:
- supervisor agent
- information agent
- booking agent
- appointment availability tools
- booking, cancellation, and rescheduling tools
- FastAPI endpoint
- Streamlit interface

Target: evolve the existing system into a production-oriented AI Customer Service Agent for a dental clinic.

## Original Audit Findings

The audit identified these confirmed critical defects:

### BUG-01 — Appointment data source mismatch
Appointment mutation functions wrote to `availability.csv` while availability lookup read from `doctor_availability.csv`. This could prevent appointment changes from persisting to the file actually used for lookup.

### BUG-02 — Appointment datetime format mismatch
`set_appointment` used a platform-specific / incompatible format similar to `%#H.%M`, while the CSV stores `DD-MM-YYYY HH:MM`. This can cause appointment matching to fail silently.

Additional risks identified by the audit:
- rescheduling was non-atomic
- concurrent booking could cause race conditions / double booking
- no authentication or authorization
- Windows-specific `%#H` behavior could break on Linux/macOS
- sensitive patient information could be exposed through logging
- missing validation/testing and other reliability gaps

## Controlled Execution Protocol

Every implementation phase must:
1. Have one clearly defined objective.
2. Specify permitted file modifications.
3. Prohibit unrelated refactoring.
4. Inspect relevant existing code before editing.
5. Implement and test the assigned phase.
6. Report changed files.
7. Report actual test results honestly.
8. Identify unresolved issues.
9. Stop after the assigned phase.
10. Wait for explicit user approval before continuing.

Never silently continue to another phase. If an unexpected architectural dependency is discovered, stop and explain before expanding scope.

## 10-Phase Roadmap

### Phase 1 — Critical Data Integrity Fixes
Repair the appointment data layer: single authoritative CSV source, correct paths, consistent datetime handling, deterministic matching, correct booking/cancellation persistence, cross-platform behavior, and focused tests using temporary fixtures.

### Phase 2 — Appointment Reliability and Atomicity
Strengthen rescheduling and appointment reliability. Prevent loss of the old appointment when the new booking fails, address concurrency risks appropriate to the current storage layer, and add transactional tests.

### Phase 3 — Validation, Error Handling, and API Hardening
Improve request validation, datetime validation, consistent API errors, exception handling, and security-sensitive logging.

### Phase 4 — FAQ / Customer Information Agent
Add grounded clinic FAQ behavior with explicit no-answer behavior and a clinic-approved content process. Do not invent clinic facts.

### Phase 5 — Appointment Integration with Customer Service Routing
Connect customer-service routing to availability, booking, cancellation, and rescheduling while keeping informational retrieval separate from transactional tools.

### Phase 6 — Conversation Memory
Add persistent conversation context, thread/session behavior, memory-aware responses, API/UI verification, and documented retention/privacy considerations.

### Phase 7 — Knowledge Base / RAG
Build a robust grounded knowledge retrieval subsystem. Semantic retrieval is now implemented and evaluated with a persistent file-based vector index, source tracking, thresholds, and synthetic metrics. Real-world activation remains dependent on an approved clinic corpus and content-owner review.

Scope:
- robust FAQ corpus loading/validation
- clinic-approved knowledge only
- embeddings and vector retrieval where justified
- metadata/source tracking
- grounded answers
- explicit insufficient-information behavior
- ingestion/indexing workflow
- synthetic retrieval evaluation set
- retrieval evaluation metrics
- tests
- documentation

Strict separation: RAG is for informational knowledge. Appointment tools remain the exact transactional source for availability, booking, cancellation, and rescheduling.

### Phase 8 — Human Escalation / Human-in-the-Loop
Add escalation criteria, handoff state, human-readable context, safe stop/resume behavior, tests, and auditability for complaints, failures, sensitive cases, and unresolved requests. The prototype now uses a local SQLite handoff queue with privacy-minimized summaries, explicit case IDs/statuses, deterministic trigger detection, truthful pending status, unresolved-FAQ escalation, and queue-failure handling. External contact-channel integration, authentication/access controls, notification, retention, and operational ownership remain production work.

### Phase 9 — Streamlit UI / Customer Experience
Complete the chat experience, history display, appointment confirmations/errors, escalation status, and clear UX for missing information and tool failures.

### Phase 10 — Production Readiness
Define and validate production data source, authentication/authorization, secret management, persistent storage, observability, deployment, health checks, CI/CD delivery/deployment, rollback, privacy/security controls, and current data refresh/source-of-truth process.

## Data Safety Rules

- Treat `data/doctor_availability.csv` as historical legacy appointment data unless an explicitly approved new source of truth is implemented.
- Never present the historical CSV as live/current availability.
- Never replace the canonical dataset with `tests/fixtures/synthetic_appointments.csv`.
- Synthetic fixtures are test-only.
- Never expose real patient identifiers in tests or logs.
- Do not invent clinic FAQ content.
- `data/clinic_faq.json` may contain only clinic-approved facts.

## Current Verified Project Position

The project has progressed beyond the original audit. Phase 7 engineering is implemented and tested: validated FAQ ingestion, OpenAI embeddings, persistent file-based vector retrieval, source metadata, content-fingerprint rebuilds, grounded thresholding, and deterministic synthetic retrieval evaluation are in place. `data/clinic_faq.json` remains intentionally empty because no clinic-approved corpus has been supplied; therefore real clinic-specific RAG activation remains blocked on clinic-owned content and review. Phase 8 prototype work is now implemented: deterministic human/complaint/sensitive escalation triggers, local SQLite handoff cases, privacy-minimized summaries, status tracking, truthful pending responses, unresolved-FAQ escalation, and failure handling are tested. Streamlit UI and production readiness remain partial/incomplete.

## Current Next Step

Phase 7 engineering is validated; real clinic-specific FAQ activation remains blocked only on clinic-approved content and review. Phase 8 local-queue prototype implementation is complete and tested. The next roadmap phase is Phase 9 — Streamlit UI / Customer Experience, after explicit approval.

For the full original audit wording, refer to the attached/source audit conversation log that established this roadmap.
