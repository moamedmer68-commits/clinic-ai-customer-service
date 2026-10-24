# Patient Registration and Identity Verification Design

**Status:** Design decision required before implementing a verification channel.
**Scope:** Development Plan Phase 1. This document does not enable production registration or assert that the application is production-ready.

## Existing behavior verified in repository

- POST /patients/register collects a name, email, phone, and password and creates a pending_review account.
- A Patient ID is not issued at initial registration; it is assigned after staff approval.
- Login creates a bearer session for an approved account.
- Staff approval currently relies on a shared configured token, not named staff accounts with role-based access control. This is a production blocker.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes, and session tokens are stored as hashes.
- Patient account storage supports SQLAlchemy. Docker Compose defines PostgreSQL, but a live PostgreSQL runtime has not been verified in the current environment.

## Proposed minimum-data registration fields

Required: full name, email, password, consent to the clinic privacy notice.
Optional until clinic policy confirms necessity: phone number.
Do not collect national ID, medical history, identity-document images, or date of birth unless the clinic's approved identity policy and legal/privacy review establish a need.

## Identity verification decision — select one before implementation

### Option A — Staff review (recommended for current repository, short-term)

1. Patient submits the registration request.
2. Account stays pending_review; no Patient ID or patient-specific access is issued.
3. An authorized staff member verifies the patient through the clinic's existing process, outside the application if necessary.
4. Named, authenticated staff member approves or rejects the request; approval creates the unique Patient ID.
5. Notify the patient through a clinic-approved channel once notification integration is configured.

Dependencies: define how the staff member confirms identity; replace the shared staff token with individual staff identities/RBAC before exposing approval endpoints beyond a trusted local environment.

### Option B — Email one-time code/link

1. Patient submits registration and verifies control of the email address using a single-use, expiring token/code.
2. Email verification proves control of the email address only; it does not by itself prove the person's identity or patient status.
3. Clinic approval is still required before issuing a Patient ID if the clinic needs to match the person to its patient records.

Dependencies: choose and configure a trusted email delivery provider, sender domain, expiration/retry policy, abuse limits, and operational ownership.

### Option C — SMS one-time code

Same principle as email verification, but through an approved SMS provider. A verified phone number alone is not proof of clinical identity.

Dependencies: choose an SMS provider, approved sender/region, budget, delivery/retry limits, and privacy/retention rules.

## Acceptance criteria for Phase 1

- Registration validation works in Arabic and English and does not expose account existence unnecessarily.
- Duplicate registrations have a defined, privacy-safe response.
- Password policy and recovery path are documented.
- Verification tokens/codes (if selected) are random, single-use, time-limited, stored safely, rate-limited, and invalidated on success or expiry.
- No Patient ID or patient-specific access is issued before the approved identity gate succeeds.
- Staff approval is authorized by named identities and least-privilege roles, not a shared token, before production exposure.
- Privacy notice/consent, retention, account deactivation, and deletion/export responsibilities are assigned to the clinic owner.
- Automated tests cover successful and failed registration, duplicates, expired/replayed verification, unauthorized approval, ID uniqueness, and cross-patient isolation.

## Decisions required from product/clinic owner

- Chosen verification method: A, B, or C.
- If A: what existing clinic process can staff use to verify the person's identity?
- If B/C: approved delivery provider and operational owner.
- Is phone number mandatory, or optional?
- What privacy notice and retention/deletion policy has the clinic approved?

Until these decisions are confirmed, do not invent an OTP vendor, collect additional sensitive identity information, or represent the registration flow as verified for production use.


## Product decision update — 2026-10-24

The product owner has explicitly chosen **no identity verification** for self-registration. Replace the earlier A/B/C verification choice with this behavior:

1. A patient creates an account using full name, email, password, and optional phone.
2. The application creates a unique Patient ID immediately and starts an authenticated session after successful registration.
3. No email OTP, SMS OTP, identity documents, or clinic-staff approval is required for registration.
4. Authentication, password hashing, login throttling, session expiration/revocation, and per-patient data isolation remain required.
5. Patient ID issuance is not proof of a person's real-world identity. Do not expose records based only on a typed Patient ID; all patient-specific actions must use the authenticated session.
6. Existing pending-review accounts should be handled compatibly; do not automatically grant access to existing accounts unless a migration/review policy is explicitly defined.

The application code and tests still need to be updated to implement and verify this behavior. Do not mark the change complete until registration returns an authenticated session, the UI signs the user in directly, duplicate registration and ID uniqueness are tested, and the full test suite passes.
