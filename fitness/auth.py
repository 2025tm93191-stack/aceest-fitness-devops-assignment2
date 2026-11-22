"""Login with roles, ported from the users table in ACEest v3.1.2 / v3.2.4.

Passwords are stored as salted hashes and clients authenticate with a signed bearer token
(``Authorization: Bearer <token>``) returned by ``POST /api/login``.
"""

from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .responses import error

ROLES = ("Admin", "Trainer")
TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60
MIN_PASSWORD_LENGTH = 8

bp = Blueprint("auth", __name__, url_prefix="/api")


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="aceest-auth")


def issue_token(username, role):
    return _serializer().dumps({"u": username, "r": role})


def ensure_admin():
    """Create the 'admin' account from ADMIN_PASSWORD if it does not exist yet."""
    password = current_app.config.get("ADMIN_PASSWORD")
    if not password:
        return
    conn = db.get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("admin", generate_password_hash(password), "Admin"),
    )
    conn.commit()


def login_required(*roles):
    """Require a valid bearer token; if roles are given, the user must hold one of them."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return error("authentication required", 401)
            try:
                claims = _serializer().loads(header[len("Bearer "):], max_age=TOKEN_MAX_AGE_SECONDS)
            except BadSignature:
                return error("invalid or expired token", 401)
            if roles and claims.get("r") not in roles:
                return error("forbidden for role " + str(claims.get("r")), 403)
            g.user = {"username": claims.get("u"), "role": claims.get("r")}
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    row = db.get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], str(data.get("password", ""))):
        return error("invalid username or password", 401)
    return jsonify({"token": issue_token(row["username"], row["role"]),
                    "username": row["username"], "role": row["role"]})


@bp.get("/me")
@login_required()
def me():
    return jsonify(g.user)


@bp.get("/users")
@login_required("Admin")
def list_users():
    rows = db.get_db().execute("SELECT username, role FROM users ORDER BY username").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/users")
@login_required("Admin")
def create_user():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = data.get("role", "Trainer")
    if not username:
        return error("username is required")
    if len(password) < MIN_PASSWORD_LENGTH:
        return error(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if role not in ROLES:
        return error(f"role must be one of {', '.join(ROLES)}")
    conn = db.get_db()
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        return error(f"User '{username}' already exists", 409)
    conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                 (username, generate_password_hash(password), role))
    conn.commit()
    return jsonify({"username": username, "role": role}), 201
