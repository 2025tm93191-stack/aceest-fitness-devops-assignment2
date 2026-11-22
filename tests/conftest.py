import pytest

from app import create_app

ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "APP_VERSION": "9.9.9-test",
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test-secret",
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def member(client):
    """A saved client used by the progress / workout / membership tests."""
    client.post("/api/clients", json={"name": "Arjun", "weight": 80, "program": "FL"})
    return "Arjun"


def _login(client, username, password):
    token = client.post("/api/login", json={"username": username, "password": password}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client):
    return _login(client, "admin", ADMIN_PASSWORD)


@pytest.fixture
def trainer_headers(client, admin_headers):
    client.post("/api/users", headers=admin_headers,
                json={"username": "coach", "password": "coach-pass-1", "role": "Trainer"})
    return _login(client, "coach", "coach-pass-1")
