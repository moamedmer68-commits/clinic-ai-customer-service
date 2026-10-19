import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def authorized_test_client(monkeypatch):
    """Build a test API client with a deterministic non-production API token."""
    test_token = "test-api-token"
    monkeypatch.setenv("API_ACCESS_TOKEN", test_token)
    monkeypatch.delenv("ALLOW_UNAUTHENTICATED_LOCAL_DEV", raising=False)
    # Legacy agent tests focus on API/service behavior; patient-session enforcement has dedicated tests.
    monkeypatch.setenv("PATIENT_AUTH_REQUIRED", "false")

    def build(app):
        client = TestClient(app)
        client.headers.update({"X-API-Key": test_token})
        return client

    return build
