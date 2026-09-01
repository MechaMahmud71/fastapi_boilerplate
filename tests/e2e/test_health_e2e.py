"""Health endpoints against the real app and database."""


def test_liveness_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}


def test_liveness_needs_no_token(client):
    """Load balancers do not authenticate."""
    assert client.get("/health").status_code == 200


def test_readiness_reports_the_database(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ready", "database": "ok"}


def test_health_uses_the_standard_envelope(client):
    body = client.get("/health").json()
    assert list(body) == ["success", "data", "message"]
    assert body["success"] is True
