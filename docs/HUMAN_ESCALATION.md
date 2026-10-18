# Human escalation and support handoff

## Purpose

Phase 8 adds a truthful human-handoff workflow for unresolved, sensitive, or explicitly escalated patient requests. The current implementation uses a local SQLite queue as the prototype handoff channel. It does not send email, SMS, WhatsApp, or create an external support ticket.

## Escalation triggers

The supervisor performs deterministic high-confidence checks before invoking the LLM router:

- Explicit request to speak to a human, representative, operator, manager, or similar support person.
- Explicit complaint/formal complaint or a request to speak with a manager.
- High-confidence urgent/severe medical wording such as severe pain, heavy bleeding, swelling, or infection.

FAQ requests that cannot be answered from the verified semantic FAQ corpus are escalated by faq_node. A semantic FAQ retrieval exception also creates a handoff case instead of claiming a successful answer.

## User-facing status contract

A successfully created case always starts with status pending.

The response states that the request was escalated to the clinic support queue, includes a case ID, and says that the current status is pending human review. The system explicitly does not claim that a human has responded.

When the local queue cannot be written, the response states that no human was contacted through the system and directs the patient to contact the clinic directly.

## Privacy minimization

The handoff record stores a bounded summary of the latest conversation turns instead of the full patient identifier. Common email addresses, long numeric identifiers, and phone-like values are redacted before persistence. An optional opaque thread_ref may be stored for correlation, but raw patient IDs are not used as the handoff case reference.

The current prototype does not provide a patient-facing lookup endpoint for case status. Operators use the local queue through the support.handoff helpers.

## Queue lifecycle

Supported states:

- pending
- acknowledged
- resolved
- cancelled

Use create_handoff_case(...) to create a case.
Use list_pending_handoffs(...) to retrieve cases awaiting human handling.
Use get_handoff_case(...) to inspect one case.
Use update_handoff_status(...) to acknowledge, resolve, or cancel a case.

## Configuration

Set HANDOFF_DB_PATH=data/human_handoffs.sqlite3

The default path is the repository data/ directory. The generated SQLite database is ignored by Git.

## Testing

Phase 8 tests are in tests/test_handoff.py.

They cover trigger detection, privacy-minimized summaries, case creation/status transitions, explicit human requests, unresolved FAQ escalation, retrieval-error escalation, and invalid status handling.

## Production limitation

The local SQLite queue is intentionally a prototype integration. Production deployment should replace it with an authenticated support system or queue with access controls, operational ownership, notification, retention/deletion policy, audit logging, and an actual human contact channel.