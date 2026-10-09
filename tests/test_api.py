from types import SimpleNamespace

from fastapi.testclient import TestClient

from main import create_app


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
