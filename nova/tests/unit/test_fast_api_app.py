from fastapi.testclient import TestClient

from app.fast_api_app import app


def test_api_index_returns_service_metadata():
    client = TestClient(app)

    response = client.get("/api")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "nova"
    assert payload["health"] == "/healthz"
    assert payload["endpoints"]["chat"] == "/api/chat"
