# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Flask + SQLite web app for ACEest Fitness & Gym (ported from the Tkinter scripts in `legacy_versions/`), with CI/CD: GitHub Actions, Jenkins (Pytest, SonarQube quality gate, Docker Hub push, Kubernetes deploy with five strategies and automatic rollback). Python 3.12+. This is BITS DevOps Assignment 2; v1.0.0 is the Assignment 1 baseline.

## Commands

```bash
pip install -r requirements-dev.txt                 # runtime + pytest, pytest-cov, flake8
ACEEST_ADMIN_PASSWORD=dev-pass python ACEest_Fitness.py   # dev server on :5000 (PORT env overrides)

pytest                                              # all tests (pytest.ini adds -v, testpaths=tests)
pytest tests/test_api.py::test_bmi_endpoint         # single test
pytest --cov --cov-report=term-missing              # coverage; source/omit/relative paths in .coveragerc

python -m compileall -q app.py ACEest_Fitness.py fitness tests   # CI syntax gate
flake8 .                                            # max-line-length 110; legacy_versions excluded
shellcheck -x k8s/scripts/*.sh                      # CI lints the deploy scripts too

docker build --target test -t aceest-fitness:test . && docker run --rm aceest-fitness:test
docker build --build-arg APP_VERSION=2.0.0 -t aceest-fitness:2.0.0 .   # runtime (gunicorn ACEest_Fitness:app)

k8s/scripts/deploy.sh <rolling|blue-green|canary|ab-testing|shadow> <image> [baseline-image]
k8s/scripts/smoke-test.sh <strategy> [expected-version]   # also rollback.sh, promote.sh, status.sh, traffic.sh
```

## Architecture

- **`ACEest_Fitness.py`** — entry point named by the assignment; re-exports `app`/`create_app` from `app.py`. Gunicorn serves `ACEest_Fitness:app`.
- **`app.py`** — `create_app(test_config)` factory; core routes in `register_routes(app)`, v2 features in blueprints `fitness/auth.py` and `fitness/tracking.py`. Module-level `app = create_app()` means importing `app` initializes the DB at `ACEEST_DB` or `instance/aceest.db`. Config comes from env: `APP_VERSION` (else `VERSION` file), `APP_TRACK`, `ACEEST_DB`, `ACEEST_SECRET_KEY`, `ACEEST_ADMIN_PASSWORD` (admin account only created when set).
- **`fitness/calculations.py`** — pure validation/calculation functions. They raise `ValueError` with user-facing messages; routes return `error(str(exc))` (from `fitness/responses.py`) → `{"error": ...}` with 400. Follow this pattern.
- **`fitness/auth.py`** — `login_required(*roles)` decorator; tokens are `itsdangerous` signatures of `{u, r}` with `SECRET_KEY`, so every replica must share `ACEEST_SECRET_KEY` (K8s Secret `aceest-secrets`).
- **`fitness/db.py`** — per-request sqlite3 connection on `flask.g`. Schema is `CREATE TABLE IF NOT EXISTS`; columns added to existing tables must also go in `ADDED_COLUMNS` so `migrate()` ALTERs old databases (tolerates concurrent pods adding the same column). `progress`/`workouts`/`metrics` reference clients by `client_name`; `exercises` by `workout_id`.
- Error conventions: 400 validation, 401 no/invalid token, 403 wrong role, 404 unknown client/program/workout, 409 duplicates.
- **`/version`** returns version, track and hostname (pod name); the K8s scripts and `traffic.sh` rely on its JSON shape.

## Testing

`tests/conftest.py` builds the app with a temp SQLite file, `APP_VERSION=9.9.9-test`, a fixed `SECRET_KEY` and an admin password; fixtures `member` (client "Arjun"), `admin_headers`, `trainer_headers`. README states the test count (currently 103) — update it when adding tests.

## Docker

Multi-stage `Dockerfile`: `test` stage copies the repo (minus `.dockerignore`, which excludes `legacy_versions`, `k8s`, Screenshots); `runtime` copies only `app.py`, `ACEest_Fitness.py`, `VERSION`, `fitness/`, `templates/` — add new runtime files there. `--build-arg APP_VERSION` bakes the version. Runs as non-root uid 10001.

## Kubernetes / Jenkins

- One namespace per strategy (`aceest-rolling`, `aceest-blue-green`, `aceest-canary`, `aceest-ab`, `aceest-shadow`), each exposed by ingress-nginx at `/<strategy>/` with regex rewrite. Manifests contain `__PLACEHOLDER__` tokens rendered by `render()` in `k8s/scripts/lib.sh` (sed), so apply them through the scripts, not `kubectl apply -f` directly.
- Scripts must stay bash 3.2 compatible (macOS Jenkins agents) and shellcheck-clean.
- Jenkinsfile credentials IDs: `dockerhub-creds`, `kubeconfig`; SonarQube server `SonarQube`, scanner tool `SonarScanner`. Blue-green failures before the selector switch need no rollback; the Jenkinsfile relies on that.

## Conventions

- Branches: `feature/`, `fix/`, `test/`, `ci/`, `docs/` prefixes; merge to `main` via PR with `--no-ff`. Release tags `vX.Y.Z` match the `VERSION` file.
- Commit messages: `type: summary` (e.g. `feat: add BMI endpoint`, `ci: run pytest inside docker`).
