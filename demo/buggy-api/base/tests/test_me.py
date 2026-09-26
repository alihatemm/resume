from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_me_returns_current_user():
    response = client.get("/me", headers={"Authorization": "Bearer demo-token"})
    assert response.status_code == 200, response.json()
    assert response.json() == {"id": 42, "name": "Maya Chen"}
