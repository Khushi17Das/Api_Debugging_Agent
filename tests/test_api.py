import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import DebugSession

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Ensure database tables are created before each test."""
    Base.metadata.create_all(bind=engine)
    yield


def test_health_check_endpoint():
    """Verify health endpoint returns healthy status and active features."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Smart Fallback Mode" in data["features"]


def test_smart_fallback_mode_on_insufficient_evidence():
    """
    CRITICAL TEST:
    When only a generic status code (500) is provided without logs or code,
    the agent MUST trigger Smart Fallback Mode and refuse to invent assumptions.
    """
    payload = {
        "status_code": 500,
        "error_message": "Internal Server Error",
    }
    response = client.post("/api/debug/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "smart_fallback"
    assert data["status"] == "needs_more_evidence"
    assert data["confidence"] == "low"
    assert data["safe_fix_mode"] == "NEEDS MORE EVIDENCE"
    assert len(data["confirmed_facts"]) > 0
    assert len(data["likely_causes"]) > 0
    assert len(data["assumptions"]) > 0
    assert len(data["missing_information"]) > 0
    assert len(data["safe_next_steps"]) > 0


def test_diagnosed_mode_on_422_validation_error():
    """
    When specific validation error evidence is provided,
    the agent enters Diagnosis Mode with high confidence.
    """
    payload = {
        "endpoint": "/api/users",
        "method": "POST",
        "status_code": 422,
        "error_message": "value is not a valid email address",
        "request_body": '{"email": "invalid-email-address"}',
    }
    response = client.post("/api/debug/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "diagnosis"
    assert data["status"] == "diagnosed"
    assert data["confidence"] == "high"
    assert data["safe_fix_mode"] == "SAFE TO SUGGEST"
    assert data["root_cause"] is not None
    assert len(data["evidence"]) >= 2
    assert data["suggested_fix"] is not None
    assert data["fixed_code"] is not None


def test_diagnosed_mode_on_sqlalchemy_log():
    """
    When server logs contain concrete exception evidence (SQLAlchemy OperationalError),
    the agent accurately identifies the database connection root cause.
    """
    payload = {
        "endpoint": "/api/orders",
        "method": "GET",
        "status_code": 500,
        "logs": "sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) could not connect to server",
    }
    response = client.post("/api/debug/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "diagnosis"
    assert data["status"] == "diagnosed"
    assert "database" in data["root_cause"].lower()
    assert any("sqlalchemy" in ev.lower() for ev in data["evidence"])


def test_history_crud_and_stats():
    """Verify session persistence in history, retrieval, stats update, and deletion."""
    payload = {
        "endpoint": "/api/test-route",
        "method": "GET",
        "status_code": 404,
        "error_message": "Not Found",
    }
    create_resp = client.post("/api/debug/analyze", json=payload)
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]
    assert session_id is not None

    hist_resp = client.get("/api/debug/history")
    assert hist_resp.status_code == 200
    items = hist_resp.json()
    assert any(item["id"] == session_id for item in items)

    detail_resp = client.get(f"/api/debug/history/{session_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == session_id
    assert detail["endpoint"] == "/api/test-route"

    stats_resp = client.get("/api/debug/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_sessions"] >= 1

    del_resp = client.delete(f"/api/debug/history/{session_id}")
    assert del_resp.status_code == 200

    not_found_resp = client.get(f"/api/debug/history/{session_id}")
    assert not_found_resp.status_code == 404


def test_safe_test_endpoint_ssrf_protection():
    """Verify that SSRF metadata IPs and invalid schemes are blocked safely."""
    # Cloud metadata IP blocked
    response = client.post(
        "/api/debug/test",
        json={"endpoint": "http://169.254.169.254/latest/meta-data/", "method": "GET"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pass_fail"] == "ERROR"
    assert "Security/Validation Error" in data["error_detail"]

    proto_resp = client.post(
        "/api/debug/test",
        json={"endpoint": "ftp://example.com/file", "method": "GET"},
    )
    assert proto_resp.status_code == 200
    assert proto_resp.json()["pass_fail"] == "ERROR"


def test_fix_verification_fallback_when_cannot_test():
    """
    CRITICAL TEST:
    If the endpoint cannot be tested, the system MUST NOT claim it is resolved.
    Instead it must say: 'Fix suggested, but automatic verification was not available.'
    """
    response = client.post(
        "/api/debug/verify",
        json={"endpoint": "not-a-valid-url", "method": "GET"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["can_test"] is False
    assert data["is_resolved"] is False
    assert data["result"] == "Fix suggested, but automatic verification was not available."


def test_sample_playground_endpoints():
    """Verify built-in playground endpoints for 404, 422, 500, and 401."""
    resp_404 = client.get("/api/sample/users/999")
    assert resp_404.status_code == 404

    resp_422 = client.post("/api/sample/users", json={"name": "Alice", "email": "invalid-email"})
    assert resp_422.status_code == 422

    resp_201 = client.post("/api/sample/users", json={"name": "Alice", "email": "alice@example.com"})
    assert resp_201.status_code == 201

    resp_401 = client.get("/api/sample/protected")
    assert resp_401.status_code == 401

    resp_auth = client.get("/api/sample/protected", headers={"Authorization": "Bearer valid_token_123"})
    assert resp_auth.status_code == 200
