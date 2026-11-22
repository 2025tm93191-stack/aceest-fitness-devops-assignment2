import sqlite3

import pytest

from app import create_app
from fitness import db
from fitness.programs import PLAN_TEMPLATES


# ---------- Metrics ----------
def test_metrics_logging_and_listing(client, member):
    resp = client.post(f"/api/clients/{member}/metrics",
                       json={"date": "2026-01-05", "weight": 82.5, "waist": 90, "bodyfat": 21.5})
    assert resp.status_code == 201
    client.post(f"/api/clients/{member}/metrics", json={"date": "2026-01-01", "weight": 83})
    rows = client.get(f"/api/clients/{member}/metrics").get_json()
    assert [r["date"] for r in rows] == ["2026-01-01", "2026-01-05"]
    assert rows[0]["waist"] is None and rows[1]["bodyfat"] == 21.5


def test_metrics_validation(client, member):
    url = f"/api/clients/{member}/metrics"
    assert client.post(url, json={}).status_code == 400
    assert client.post(url, json={"weight": 80, "bodyfat": 120}).status_code == 400
    assert client.post(url, json={"weight": 80, "date": "05/01/2026"}).status_code == 400


def test_metrics_unknown_client(client):
    assert client.get("/api/clients/Nobody/metrics").status_code == 404


# ---------- Exercises ----------
def _workout_id(client, member):
    resp = client.post(f"/api/clients/{member}/workouts",
                       json={"workout_type": "Strength", "duration_min": 60})
    return resp.get_json()["id"]


def test_workout_ids_are_returned(client, member):
    workout_id = _workout_id(client, member)
    assert client.get(f"/api/clients/{member}/workouts").get_json()[0]["id"] == workout_id


def test_exercises_logging(client, member):
    workout_id = _workout_id(client, member)
    url = f"/api/clients/{member}/workouts/{workout_id}/exercises"
    resp = client.post(url, json={"name": "Back Squat", "sets": 5, "reps": 5, "weight": 100})
    assert resp.status_code == 201
    client.post(url, json={"name": "Push-ups", "sets": 3, "reps": 20})
    rows = client.get(url).get_json()
    assert [r["name"] for r in rows] == ["Back Squat", "Push-ups"]
    assert rows[1]["weight"] is None


def test_exercise_validation(client, member):
    url = f"/api/clients/{member}/workouts/{_workout_id(client, member)}/exercises"
    assert client.post(url, json={"sets": 3, "reps": 5}).status_code == 400
    assert client.post(url, json={"name": "Row", "sets": 0, "reps": 5}).status_code == 400
    assert client.post(url, json={"name": "Row", "sets": 3, "reps": 5, "weight": -10}).status_code == 400


def test_exercises_for_unknown_or_foreign_workout(client, member):
    workout_id = _workout_id(client, member)
    client.post("/api/clients", json={"name": "Meera"})
    assert client.get(f"/api/clients/Meera/workouts/{workout_id}/exercises").status_code == 404
    assert client.get(f"/api/clients/{member}/workouts/999/exercises").status_code == 404


# ---------- Targets on client creation ----------
def test_client_targets_are_stored(client):
    resp = client.post("/api/clients", json={"name": "Kavya", "target_weight": 60, "target_adherence": 90})
    assert resp.status_code == 201
    assert resp.get_json()["target_weight"] == 60 and resp.get_json()["target_adherence"] == 90


def test_client_targets_validation(client):
    assert client.post("/api/clients", json={"name": "K", "target_weight": -1}).status_code == 400
    assert client.post("/api/clients", json={"name": "K", "target_adherence": 150}).status_code == 400


# ---------- Program generator ----------
def test_generate_program_requires_login(client, member):
    assert client.post(f"/api/clients/{member}/generate-program").status_code == 401


def test_generate_program_uses_client_program(client, member, trainer_headers):
    resp = client.post(f"/api/clients/{member}/generate-program", headers=trainer_headers)
    data = resp.get_json()
    assert resp.status_code == 200 and data["goal"] == "FL"
    assert data["plan"] in PLAN_TEMPLATES["FL"]
    assert client.get(f"/api/clients/{member}").get_json()["generated_plan"] == data["plan"]


def test_generate_program_with_explicit_or_random_goal(client, admin_headers):
    client.post("/api/clients", json={"name": "Ravi"})
    url = "/api/clients/Ravi/generate-program"
    assert client.post(url, headers=admin_headers, json={"goal": "mg"}).get_json()["goal"] == "MG"
    assert client.post(url, headers=admin_headers).get_json()["goal"] in PLAN_TEMPLATES
    assert client.post(url, headers=admin_headers, json={"goal": "XX"}).status_code == 400


def test_generate_program_unknown_client(client, admin_headers):
    assert client.post("/api/clients/Nobody/generate-program", headers=admin_headers).status_code == 404


# ---------- PDF report ----------
def test_pdf_report(client, member):
    client.post(f"/api/clients/{member}/progress", json={"week": "W1", "adherence": 80})
    client.post(f"/api/clients/{member}/workouts", json={"workout_type": "Cardio", "duration_min": 30})
    client.post(f"/api/clients/{member}/metrics", json={"weight": 79})
    resp = client.get(f"/api/clients/{member}/report.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")
    assert 'filename="Arjun_report.pdf"' in resp.headers["Content-Disposition"]


def test_pdf_report_for_empty_client_with_unicode_name(client):
    client.post("/api/clients", json={"name": "Śrī"})
    resp = client.get("/api/clients/Śrī/report.pdf")
    assert resp.status_code == 200 and resp.data.startswith(b"%PDF")
    assert client.get("/api/clients/Nobody/report.pdf").status_code == 404


# ---------- Schema migration from a v1.x database ----------
def test_v1_database_is_migrated(tmp_path):
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,"
                 " age INTEGER, height REAL, weight REAL, program TEXT, calories INTEGER,"
                 " membership_status TEXT DEFAULT 'Active', membership_end TEXT)")
    conn.execute("INSERT INTO clients (name) VALUES ('Old')")
    conn.commit()
    conn.close()
    client = create_app({"TESTING": True, "DATABASE": str(path)}).test_client()
    data = client.get("/api/clients/Old").get_json()
    assert data["name"] == "Old" and "generated_plan" in data
    # Starting again on the already migrated database must not fail.
    create_app({"TESTING": True, "DATABASE": str(path)})


def test_track_is_reported(client):
    assert client.get("/version").get_json()["track"] == "default"


class _RacingConnection:
    """Pretends the columns are missing, then fails the ALTER as if another pod added them."""

    def __init__(self, message):
        self.message = message

    def execute(self, sql):
        if sql.startswith("PRAGMA"):
            return []
        raise sqlite3.OperationalError(self.message)

    def commit(self):
        pass


def test_migration_tolerates_concurrent_column_add():
    db.migrate(_RacingConnection("duplicate column name: target_weight"))


def test_migration_reraises_other_errors():
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(_RacingConnection("disk I/O error"))
