from app import create_app


def test_admin_can_log_in(client, admin_headers):
    assert client.get("/api/me", headers=admin_headers).get_json() == {"username": "admin", "role": "Admin"}


def test_login_rejects_wrong_password(client):
    resp = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_rejects_unknown_user_and_empty_body(client):
    assert client.post("/api/login", json={"username": "ghost", "password": "x"}).status_code == 401
    assert client.post("/api/login").status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/me").status_code == 401


def test_me_rejects_tampered_token(client, admin_headers):
    bad = {"Authorization": admin_headers["Authorization"] + "x"}
    assert client.get("/api/me", headers=bad).status_code == 401


def test_token_from_other_secret_is_rejected(tmp_path, client, admin_headers):
    other = create_app({"TESTING": True, "DATABASE": str(tmp_path / "other.db"), "SECRET_KEY": "different"})
    assert other.test_client().get("/api/me", headers=admin_headers).status_code == 401


def test_admin_creates_trainer_who_can_log_in(client, trainer_headers):
    assert client.get("/api/me", headers=trainer_headers).get_json()["role"] == "Trainer"


def test_admin_lists_users_without_password_hashes(client, admin_headers, trainer_headers):
    users = client.get("/api/users", headers=admin_headers).get_json()
    assert users == [{"username": "admin", "role": "Admin"}, {"username": "coach", "role": "Trainer"}]


def test_trainer_cannot_manage_users(client, trainer_headers):
    assert client.get("/api/users", headers=trainer_headers).status_code == 403
    resp = client.post("/api/users", headers=trainer_headers,
                       json={"username": "x", "password": "long-enough", "role": "Admin"})
    assert resp.status_code == 403


def test_create_user_validation(client, admin_headers):
    def post(body):
        return client.post("/api/users", headers=admin_headers, json=body).status_code

    assert post({"password": "long-enough"}) == 400
    assert post({"username": "a", "password": "short"}) == 400
    assert post({"username": "a", "password": "long-enough", "role": "Owner"}) == 400
    assert post({"username": "admin", "password": "long-enough"}) == 409


def test_no_admin_without_password(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "x.db"), "ADMIN_PASSWORD": None})
    resp = app.test_client().post("/api/login", json={"username": "admin", "password": ""})
    assert resp.status_code == 401
