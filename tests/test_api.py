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


def test_execute_valid_request_uses_hashed_thread_and_consistent_response(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    graph = SuccessfulGraph()
    with TestClient(create_app()) as client:
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


def test_execute_invalid_payload_has_safe_validation_contract(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        response = client.post("/execute", json={"id_number": 12, "messages": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Invalid request"
    assert "request_id" in body
    assert all(set(error) <= {"loc", "msg", "type"} for error in body["error"]["details"])


def test_execute_graph_failure_returns_safe_500(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        client.app.state.graph = FailingGraph()
        response = client.post("/execute", json={"id_number": 1234567, "messages": "hello"})
    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "agent_execution_failed",
        "message": "The request could not be processed.",
    }


def test_execute_serializes_json_compatible_message_content(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        client.app.state.graph = StructuredMessageGraph()
        response = client.post("/execute", json={"id_number": 1234567, "messages": "hello"})
    assert response.status_code == 200
    assert response.json()["messages"] == [{"type": "ai", "content": {"answer": "Hello"}}]


def test_execute_returns_handoff_status_for_frontend(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        client.app.state.graph = EscalationGraph()
        response = client.post("/execute", json={"id_number": 1234567, "messages": "connect me to a person"})
    assert response.status_code == 200
    assert response.json()["escalation"] == {
        "status": "pending",
        "case_id": "HND-20261009-ABC123",
        "trigger": "human_requested",
    }
