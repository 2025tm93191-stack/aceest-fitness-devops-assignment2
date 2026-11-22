"""v2.0 client features ported from ACEest v2.2.4 - v3.2.4: body metrics, exercises per
workout, the program generator and the PDF report."""

from datetime import date

from flask import Blueprint, Response, current_app, jsonify, request

from . import db
from .auth import login_required
from .calculations import validate_exercise, validate_metrics
from .programs import generate_plan
from .reports import build_client_report
from .responses import error

bp = Blueprint("tracking", __name__, url_prefix="/api/clients")


def _client_or_404(conn, name):
    row = conn.execute("SELECT * FROM clients WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def _iso_date(value):
    value = value or date.today().isoformat()
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("date must be in YYYY-MM-DD format")
    return value


# ---------- Body metrics ----------
@bp.route("/<name>/metrics", methods=["GET", "POST"])
def metrics(name):
    conn = db.get_db()
    if not db.client_exists(conn, name):
        return error(f"Client '{name}' not found", 404)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            values = validate_metrics(data)
            values["date"] = _iso_date(data.get("date"))
        except ValueError as exc:
            return error(str(exc))
        conn.execute(
            "INSERT INTO metrics (client_name, date, weight, waist, bodyfat) VALUES (?, ?, ?, ?, ?)",
            (name, values["date"], values["weight"], values["waist"], values["bodyfat"]),
        )
        conn.commit()
        return jsonify({"client": name, **values}), 201
    rows = conn.execute(
        "SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name = ? ORDER BY date, id", (name,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------- Exercises within a workout ----------
@bp.route("/<name>/workouts/<int:workout_id>/exercises", methods=["GET", "POST"])
def exercises(name, workout_id):
    conn = db.get_db()
    workout = conn.execute(
        "SELECT id FROM workouts WHERE id = ? AND client_name = ?", (workout_id, name)
    ).fetchone()
    if workout is None:
        return error(f"Workout {workout_id} not found for client '{name}'", 404)
    if request.method == "POST":
        try:
            values = validate_exercise(request.get_json(silent=True) or {})
        except ValueError as exc:
            return error(str(exc))
        cur = conn.execute(
            "INSERT INTO exercises (workout_id, name, sets, reps, weight) VALUES (?, ?, ?, ?, ?)",
            (workout_id, values["name"], values["sets"], values["reps"], values["weight"]),
        )
        conn.commit()
        return jsonify({"id": cur.lastrowid, "workout_id": workout_id, **values}), 201
    rows = conn.execute(
        "SELECT id, name, sets, reps, weight FROM exercises WHERE workout_id = ? ORDER BY id", (workout_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------- Program generator (trainers and admins only) ----------
@bp.post("/<name>/generate-program")
@login_required("Admin", "Trainer")
def generate_program(name):
    conn = db.get_db()
    client = _client_or_404(conn, name)
    if client is None:
        return error(f"Client '{name}' not found", 404)
    data = request.get_json(silent=True) or {}
    try:
        goal, plan = generate_plan(data.get("goal") or client.get("program"))
    except ValueError as exc:
        return error(str(exc))
    conn.execute("UPDATE clients SET generated_plan = ? WHERE name = ?", (plan, name))
    conn.commit()
    return jsonify({"client": name, "goal": goal, "plan": plan})


# ---------- PDF report ----------
@bp.get("/<name>/report.pdf")
def report(name):
    conn = db.get_db()
    client = _client_or_404(conn, name)
    if client is None:
        return error(f"Client '{name}' not found", 404)

    def rows(sql):
        return [dict(r) for r in conn.execute(sql, (name,)).fetchall()]

    pdf = build_client_report(
        client,
        rows("SELECT week, adherence FROM progress WHERE client_name = ? ORDER BY id"),
        rows("SELECT date, workout_type, duration_min, notes FROM workouts"
             " WHERE client_name = ? ORDER BY date"),
        rows("SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name = ? ORDER BY date, id"),
        version=current_app.config["APP_VERSION"],
    )
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe_name}_report.pdf"'})
