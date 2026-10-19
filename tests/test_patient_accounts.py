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


