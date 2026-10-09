import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

import main as main_module
from main import create_app
from support.pending_actions import create_pending_action, get_pending_action
from utils.session import make_thread_id


class SuccessfulGraph:
    def __init__(self):
        self.calls = []

    def invoke(self, payload, config):
        self.calls.append((payload, config))
        return {"messages": [SimpleNamespace(type="ai", content="Hello")]}


class FailingGraph:
    def invoke(self, payload, config):
        raise RuntimeError("provider failure")


class StructuredMessageGraph:
    def invoke(self, payload, config):
        return {"messages": [SimpleNamespace(type="ai", content={"answer": "Hello"})]}


class EscalationGraph:
    def invoke(self, payload, config):
        assert payload["escalation_status"] == ""
        assert payload["escalation_case_id"] == ""
        return {
            "messages": [SimpleNamespace(type="ai", content="Case is pending review.")],
            "escalation_case_id": "HND-20261009-ABC123",
            "escalation_status": "pending",
            "escalation_trigger": "human_requested",
        }


def test_health_reports_missing_configuration_without_exposing_details(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "health-check"})
    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == "health-check"
    assert response.json() == {
        "error": {"code": "service_unavailable", "message": "Service dependencies are unavailable."},
        "request_id": "health-check",
    }


def test_liveness_does_not_depend_on_model_or_api_token(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_requires_graph_and_token(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        unavailable = client.get("/health/ready")
        client.app.state.graph = SuccessfulGraph()
        missing_token = client.get("/health/ready")
        monkeypatch.setenv("API_ACCESS_TOKEN", "readiness-test-token")
        ready = client.get("/health/ready")
    assert unavailable.status_code == 503
    assert missing_token.status_code == 503
    assert ready.status_code == 200
    assert ready.json()["api_auth"] == "enabled"


def test_execute_requires_configured_api_token(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ALLOW_UNAUTHENTICATED_LOCAL_DEV", raising=False)
    with TestClient(create_app()) as client:
        response = client.post("/execute", json={"id_number": 1234567, "messages": "hello"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_auth_not_configured"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_execute_rejects_invalid_api_token(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("API_ACCESS_TOKEN", "configured-test-token")
    with TestClient(create_app()) as client:
        response = client.post(
            "/execute",
            json={"id_number": 1234567, "messages": "hello"},
            headers={"X-API-Key": "incorrect-token", "X-Request-ID": "auth-test-1"},
        )
    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "unauthorized",
        "message": "Valid API credentials are required.",
    }
    assert response.headers["X-Request-ID"] == "auth-test-1"


def test_execute_valid_request_uses_hashed_thread_and_consistent_response(authorized_test_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    graph = SuccessfulGraph()
    with authorized_test_client(create_app()) as client:
        client.app.state.graph = graph
        response = client.post(
            "/execute",
            json={"id_number": 1234567, "messages": "hello", "session_id": "session-a"},
            headers={"X-Request-ID": "request-123"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-a",
        "messages": [{"type": "ai", "content": "Hello"}],
        "request_id": "request-123",
    }
    assert graph.calls[0][1]["configurable"]["thread_id"] != "1234567:session-a"


def test_execute_invalid_payload_has_safe_validation_contract(authorized_test_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with authorized_test_client(create_app()) as client:
        response = client.post("/execute", json={"id_number": 12, "messages": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Invalid request"
    assert "request_id" in body
    assert all(set(error) <= {"loc", "msg", "type"} for error in body["error"]["details"])


def test_execute_graph_failure_returns_safe_500(authorized_test_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with authorized_test_client(create_app()) as client:
        client.app.state.graph = FailingGraph()
        response = client.post("/execute", json={"id_number": 1234567, "messages": "hello"})
    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "agent_execution_failed",
        "message": "The request could not be processed.",
    }


def test_execute_serializes_json_compatible_message_content(authorized_test_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with authorized_test_client(create_app()) as client:
        client.app.state.graph = StructuredMessageGraph()
        response = client.post("/execute", json={"id_number": 1234567, "messages": "hello"})
    assert response.status_code == 200
    assert response.json()["messages"] == [{"type": "ai", "content": {"answer": "Hello"}}]


def test_execute_returns_handoff_status_for_frontend(authorized_test_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with authorized_test_client(create_app()) as client:
        client.app.state.graph = EscalationGraph()
        response = client.post("/execute", json={"id_number": 1234567, "messages": "connect me to a person"})
    assert response.status_code == 200
    assert response.json()["escalation"] == {
        "status": "pending",
        "case_id": "HND-20261009-ABC123",
        "trigger": "human_requested",
    }


def test_local_unauthenticated_mode_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_LOCAL_DEV", "true")
    graph = SuccessfulGraph()
    with TestClient(create_app()) as client:
        client.app.state.graph = graph
        response = client.post("/execute", json={"id_number": 1234567, "messages": "hello"})
    assert response.status_code == 200


class CheckpointingGraph:
    def __init__(self):
        self.state = {"messages": []}
        self.calls = []

    def invoke(self, payload, config):
        self.calls.append((payload, config))
        return {"messages": [SimpleNamespace(type="ai", content="Normal graph response.")]}

    def update_state(self, config, values):
        self.state["messages"] = list(self.state.get("messages", [])) + list(values.get("messages", []))
        self.state.update({key: value for key, value in values.items() if key != "messages"})
        return config

    def get_state(self, config):
        return SimpleNamespace(values=self.state)


def test_api_executes_only_the_stored_pending_action_after_exact_confirmation(
    authorized_test_client, monkeypatch, tmp_path
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    patient_id = 9123456
    session_id = "approval-session"
    thread_ref = make_thread_id(patient_id, session_id)
    action, _ = create_pending_action(
        thread_ref,
        "book",
        {"doctor_name": "john doe", "desired_date": "12-10-2026 09:00"},
    )
    graph = CheckpointingGraph()
    calls = []

    def fake_booking_tool(args):
        calls.append(args)
        return "Successfully done"

    monkeypatch.setattr(main_module, "set_appointment", SimpleNamespace(invoke=fake_booking_tool))

    with authorized_test_client(create_app()) as client:
        client.app.state.graph = graph
        response = client.post(
            "/execute",
            json={"id_number": patient_id, "session_id": session_id, "messages": "YES"},
        )

    assert response.status_code == 200
    assert "Confirmed and completed" in response.json()["messages"][-1]["content"]
    assert len(calls) == 1
    assert calls[0]["doctor_name"] == "john doe"
    assert calls[0]["desired_date"].date == "12-10-2026 09:00"
    assert calls[0]["id_number"].id == patient_id
    assert graph.calls == []  # The LLM graph did not decide or execute the mutation.
    assert get_pending_action(thread_ref) is None
    connection = main_module.sqlite3.connect(str(tmp_path / "pending.sqlite3"))
    try:
        status = connection.execute(
            "SELECT status FROM pending_appointment_actions WHERE action_id = ?", (action["action_id"],)
        ).fetchone()[0]
    finally:
        connection.close()
    assert status == "executed"


def test_api_does_not_execute_ambiguous_confirmation(authorized_test_client, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    patient_id = 9123456
    session_id = "ambiguous-session"
    thread_ref = make_thread_id(patient_id, session_id)
    create_pending_action(
        thread_ref,
        "book",
        {"doctor_name": "john doe", "desired_date": "12-10-2026 09:00"},
    )
    graph = CheckpointingGraph()
    calls = []
    monkeypatch.setattr(main_module, "set_appointment", SimpleNamespace(invoke=lambda args: calls.append(args) or "Successfully done"))

    with authorized_test_client(create_app()) as client:
        client.app.state.graph = graph
        response = client.post(
            "/execute",
            json={
                "id_number": patient_id,
                "session_id": session_id,
                "messages": "yes, but make it tomorrow",
            },
        )

    assert response.status_code == 200
    assert "exact message YES" in response.json()["messages"][-1]["content"]
    assert calls == []
    assert get_pending_action(thread_ref) is not None
    assert graph.calls == []


def test_api_confirmation_is_scoped_to_patient_and_session(authorized_test_client, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    patient_id = 9123456
    original_session = "original-session"
    thread_ref = make_thread_id(patient_id, original_session)
    create_pending_action(
        thread_ref,
        "book",
        {"doctor_name": "john doe", "desired_date": "12-10-2026 09:00"},
    )
    graph = CheckpointingGraph()
    calls = []
    monkeypatch.setattr(main_module, "set_appointment", SimpleNamespace(invoke=lambda args: calls.append(args) or "Successfully done"))

    with authorized_test_client(create_app()) as client:
        client.app.state.graph = graph
        response = client.post(
            "/execute",
            json={"id_number": patient_id, "session_id": "different-session", "messages": "YES"},
        )

    assert response.status_code == 200
    assert calls == []
    assert graph.calls  # Without the matching scoped pending action, normal conversation handling is used.
    assert get_pending_action(thread_ref) is not None


def test_api_negative_confirmation_cancels_pending_action_without_mutating(
    authorized_test_client, monkeypatch, tmp_path
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    patient_id = 9123456
    session_id = "reject-session"
    thread_ref = make_thread_id(patient_id, session_id)
    create_pending_action(
        thread_ref,
        "book",
        {"doctor_name": "john doe", "desired_date": "12-10-2026 09:00"},
    )
    graph = CheckpointingGraph()
    calls = []
    monkeypatch.setattr(main_module, "set_appointment", SimpleNamespace(invoke=lambda args: calls.append(args) or "Successfully done"))

    with authorized_test_client(create_app()) as client:
        client.app.state.graph = graph
        response = client.post(
            "/execute",
            json={"id_number": patient_id, "session_id": session_id, "messages": "NO"},
        )

    assert response.status_code == 200
    assert "No appointment change was made" in response.json()["messages"][-1]["content"]
    assert calls == []
    assert get_pending_action(thread_ref) is None


def test_confirmed_api_action_books_only_in_an_isolated_synthetic_schedule(
    authorized_test_client, monkeypatch, tmp_path
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PENDING_ACTION_DB_PATH", str(tmp_path / "pending.sqlite3"))
    sample_schedule = Path(__file__).resolve().parents[1] / "deployment" / "demo_data" / "doctor_availability.csv"
    original_bytes = sample_schedule.read_bytes()
    isolated_schedule = tmp_path / "appointments.csv"
    shutil.copyfile(sample_schedule, isolated_schedule)
    monkeypatch.setenv("APPOINTMENT_CSV_PATH", str(isolated_schedule))

    patient_id = 9123456
    session_id = "synthetic-integration-session"
    thread_ref = make_thread_id(patient_id, session_id)
    create_pending_action(
        thread_ref,
        "book",
        {"doctor_name": "john doe", "desired_date": "12-10-2026 09:00"},
    )
    graph = CheckpointingGraph()

    with authorized_test_client(create_app()) as client:
        client.app.state.graph = graph
        response = client.post(
            "/execute",
            json={"id_number": patient_id, "session_id": session_id, "messages": "YES"},
        )

    assert response.status_code == 200
    assert "Confirmed and completed" in response.json()["messages"][-1]["content"]
    saved = pd.read_csv(isolated_schedule)
    row = saved.loc[saved["date_slot"] == "12-10-2026 09:00"].iloc[0]
    assert not bool(row["is_available"])
    assert int(row["patient_to_attend"]) == patient_id
    assert sample_schedule.read_bytes() == original_bytes  # The committed fake fixture was not mutated.
