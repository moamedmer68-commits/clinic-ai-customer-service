from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("API_ACCESS_TOKEN", "test-service-token")
    monkeypatch.setenv("STAFF_REVIEW_TOKEN", "test-staff-review-token")
    monkeypatch.setenv("PATIENT_AUTH_REQUIRED", "true")
    monkeypatch.setenv("PATIENT_DATABASE_URL", f"sqlite:///{(tmp_path / 'patients.sqlite3').as_posix()}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return TestClient(create_app())


def _register(client, email="patient@example.test"):
    return client.post("/patients/register", json={
        "full_name": "Test Patient",
        "email": email,
        "phone": "+201000000000",
        "password": "A-long-test-password-123",
    })


def _approve(client, account_id):
    return client.post(
        f"/staff/registrations/{account_id}/approve",
        headers={"X-Staff-Review-Key": "test-staff-review-token"},
    )


def test_registration_waits_for_staff_review_and_patient_id_is_created_only_after_approval(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        registered = _register(client)
        assert registered.status_code == 202
        assert registered.json()["status"] == "pending_review"
        assert "patient_id" not in registered.json()

        denied_login = client.post("/patients/login", json={
            "email": "patient@example.test",
            "password": "A-long-test-password-123",
        })
        assert denied_login.status_code == 403
        assert denied_login.json()["error"]["code"] == "account_not_approved"

        pending = client.get("/staff/pending-registrations", headers={
            "X-Staff-Review-Key": "test-staff-review-token",
        })
        assert pending.status_code == 200
        account_id = pending.json()["items"][0]["account_id"]

        approved = _approve(client, account_id)
        assert approved.status_code == 200
        patient_id = approved.json()["patient"]["patient_id"]
        assert patient_id.isdigit() and len(patient_id) == 8
        assert approved.json()["patient"]["status"] == "approved"


def test_login_me_logout_and_revocation(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        assert _register(client).status_code == 202
        pending = client.get("/staff/pending-registrations", headers={
            "X-Staff-Review-Key": "test-staff-review-token",
        }).json()["items"][0]
        _approve(client, pending["account_id"])

        login = client.post("/patients/login", json={
            "email": "patient@example.test",
            "password": "A-long-test-password-123",
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert token and login.json()["patient"]["patient_id"].isdigit()

        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/patients/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["patient"]["patient_id"] == login.json()["patient"]["patient_id"]

        logout = client.post("/patients/logout", headers=headers)
        assert logout.status_code == 200
        assert client.get("/patients/me", headers=headers).status_code == 401


def test_duplicate_registration_and_staff_review_authorization(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        assert _register(client).status_code == 202
        assert _register(client).status_code == 409
        assert client.get("/staff/pending-registrations").status_code == 401
        assert client.post(
            "/staff/registrations/1/approve",
            headers={"X-Staff-Review-Key": "wrong"},
        ).status_code == 401


def test_execute_requires_authenticated_patient_and_rejects_identity_mismatch(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        missing = client.post("/execute", headers={"X-API-Key": "test-service-token"}, json={"id_number": 1234567, "messages": "hello"})
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "unauthorized_patient"

        assert _register(client).status_code == 202
        pending = client.get("/staff/pending-registrations", headers={
            "X-Staff-Review-Key": "test-staff-review-token",
        }).json()["items"][0]
        _approve(client, pending["account_id"])
        login = client.post("/patients/login", json={
            "email": "patient@example.test",
            "password": "A-long-test-password-123",
        }).json()
        response = client.post(
            "/execute",
            headers={"X-API-Key": "test-service-token", "Authorization": f"Bearer {login['access_token']}"},
            json={"id_number": 1234567, "messages": "hello"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "patient_identity_mismatch"


def test_invalid_password_and_expired_session_are_not_accepted(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        _register(client)
        pending = client.get("/staff/pending-registrations", headers={
            "X-Staff-Review-Key": "test-staff-review-token",
        }).json()["items"][0]
        _approve(client, pending["account_id"])
        bad = client.post("/patients/login", json={
            "email": "patient@example.test",
            "password": "wrong-password",
        })
        assert bad.status_code == 401




def test_expired_patient_session_is_rejected(monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from patient_accounts import PatientSession

    with _client(monkeypatch, tmp_path) as client:
        assert _register(client).status_code == 202
        pending = client.get("/staff/pending-registrations", headers={
            "X-Staff-Review-Key": "test-staff-review-token",
        }).json()["items"][0]
        assert _approve(client, pending["account_id"]).status_code == 200
        login = client.post("/patients/login", json={
            "email": "patient@example.test",
            "password": "A-long-test-password-123",
        })
        token = login.json()["access_token"]
        factory = client.app.state.patient_session_factory
        with factory() as db:
            session_row = db.scalar(select(PatientSession))
            session_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        response = client.get("/patients/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_two_patients_cannot_use_each_others_ids_and_ids_are_unique(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        assert _register(client, "one@example.test").status_code == 202
        assert _register(client, "two@example.test").status_code == 202
        pending_response = client.get("/staff/pending-registrations", headers={
            "X-Staff-Review-Key": "test-staff-review-token",
        })
        pending = pending_response.json()["items"]
        assert len(pending) == 2
        approved = [_approve(client, row["account_id"]).json()["patient"] for row in pending]
        patient_ids = [row["patient_id"] for row in approved]
        assert len(set(patient_ids)) == 2
        assert all(value.isdigit() and len(value) == 8 for value in patient_ids)

        tokens = []
        for email in ("one@example.test", "two@example.test"):
            response = client.post("/patients/login", json={
                "email": email,
                "password": "A-long-test-password-123",
            })
            assert response.status_code == 200
            tokens.append(response.json()["access_token"])

        for token, other_patient_id in ((tokens[0], patient_ids[1]), (tokens[1], patient_ids[0])):
            response = client.post("/execute", headers={
                "X-API-Key": "test-service-token",
                "Authorization": f"Bearer {token}",
            }, json={"id_number": int(other_patient_id), "messages": "hello", "session_id": "shared-session-name"})
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "patient_identity_mismatch"


def test_conversation_checkpoint_keys_are_scoped_by_patient_even_for_same_session_id():
    from utils.session import make_thread_id

    shared_session_id = "a-session-id-that-is-not-a-secret"
    first = make_thread_id(12345678, shared_session_id)
    second = make_thread_id(87654321, shared_session_id)
    assert first != second
    assert len(first) == 64
    assert len(second) == 64

