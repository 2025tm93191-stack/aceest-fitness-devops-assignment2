# ACEest Fitness & Gym — Flask App with a Full CI/CD Pipeline

A Flask web application for ACEest Fitness & Gym, built from the baseline `Aceestver` Tkinter scripts, with an automated pipeline: **GitHub → Jenkins (Pytest, SonarQube quality gate) → Docker Hub → Kubernetes**, deployed with five strategies (rolling update, blue-green, canary, A/B testing, shadow) and automatic rollback.

[![CI Pipeline](https://github.com/2025tm93191-stack/aceest-fitness-devops-assignment2/actions/workflows/main.yml/badge.svg)](https://github.com/2025tm93191-stack/aceest-fitness-devops-assignment2/actions/workflows/main.yml)

## Features

| Since | Feature |
|---|---|
| v1.0.0 | Program catalogue (Fat Loss, Muscle Gain, Beginner) with workout and diet plans |
| v1.0.0 | Calorie estimator (body weight × program factor) and BMI calculator |
| v1.0.0 | Clients with membership status and expiry, weekly adherence tracking, workout log |
| v1.1.0 | `/version` endpoint: version, deployment track and pod name (used by every deployment strategy) |
| v2.0.0 | Login with roles (Admin, Trainer) and signed bearer tokens |
| v2.0.0 | Body metrics (weight, waist, body fat), exercises per workout, client targets |
| v2.0.0 | Program generator and a PDF client report |

The original desktop scripts are kept in [legacy_versions/](legacy_versions/), with a table of which version introduced what.

## Project Structure

```
aceest-fitness-devops-assignment2/
├── ACEest_Fitness.py         # Entry point (gunicorn ACEest_Fitness:app)
├── app.py                    # Flask app factory and core routes
├── VERSION                   # Application version (baked into the image)
├── fitness/
│   ├── programs.py           # Program catalogue, plan generator
│   ├── calculations.py       # Calorie, BMI, adherence and input validation (pure functions)
│   ├── auth.py               # Login, roles, tokens (blueprint)
│   ├── tracking.py           # Metrics, exercises, program generator, PDF report (blueprint)
│   ├── reports.py            # PDF builder
│   └── db.py                 # SQLite connection, schema and migration
├── templates/index.html      # Home page
├── tests/                    # Pytest suite (unit + API tests)
├── legacy_versions/          # Original Aceestver-*.py desktop scripts
├── Dockerfile                # Multi-stage build: test + slim runtime
├── Jenkinsfile               # Jenkins CI/CD pipeline
├── sonar-project.properties  # SonarQube analysis settings
├── k8s/                      # Kubernetes manifests and deploy/rollback scripts
├── .github/workflows/main.yml
├── requirements.txt          # Runtime dependencies
└── requirements-dev.txt      # Test and lint tools
```

## Local Setup

Requires Python 3.12+.

```bash
git clone https://github.com/2025tm93191-stack/aceest-fitness-devops-assignment2.git
cd aceest-fitness-devops-assignment2
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export ACEEST_ADMIN_PASSWORD='choose-a-password'   # creates the 'admin' login
python ACEest_Fitness.py
```

Open http://localhost:5000.

| Variable | Purpose | Default |
|---|---|---|
| `APP_VERSION` | Version reported by the app | contents of `VERSION` |
| `APP_TRACK` | Deployment track shown in `/version` (stable, canary, blue, ...) | `default` |
| `ACEEST_DB` | SQLite file | `instance/aceest.db` |
| `ACEEST_ADMIN_PASSWORD` | Password of the built-in `admin` account | unset: no admin account |
| `ACEEST_SECRET_KEY` | Key that signs login tokens (must be shared by all replicas) | random per process |

## Running Tests Manually

```bash
pytest                                              # run all tests
pytest tests/test_api.py                            # one file
pytest tests/test_api.py::test_bmi_endpoint         # one test
pytest --cov --cov-report=term-missing              # with coverage (settings in .coveragerc)
flake8 .                                            # lint
shellcheck -x k8s/scripts/*.sh                      # lint the deployment scripts
```

The suite has 103 tests: unit tests for the pure logic in `fitness/` and API tests that drive every endpoint through Flask's test client, including validation errors, 401/403 for roles, 404s, 409s, PDF generation and migrating a v1 database. Each test gets its own temporary SQLite database. Coverage is 100%.

## Running with Docker

```bash
docker build --build-arg APP_VERSION=2.0.0 -t aceest-fitness:2.0.0 .   # runtime image (default target)
docker run -p 5000:5000 -e ACEEST_ADMIN_PASSWORD=change-me aceest-fitness:2.0.0

docker build --target test -t aceest-fitness:test . # test image
docker run --rm aceest-fitness:test                 # runs Pytest inside the container
```

The Dockerfile uses `python:3.12-slim`, a multi-stage build so test tools never reach the runtime image, a non-root user, no pip cache, a `.dockerignore`, OCI labels and a health check. The app runs under Gunicorn instead of the Flask dev server.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check (includes app version) |
| GET | `/version` | App version, deployment track and hostname (pod name in Kubernetes) |
| GET | `/api/programs` | List programs |
| GET | `/api/programs/<code>` | Program detail (`FL`, `MG`, `BG`) |
| POST | `/api/calories` | `{"weight_kg": 70, "program": "FL"}` |
| POST | `/api/bmi` | `{"height_cm": 175, "weight_kg": 70}` |
| GET / POST | `/api/clients` | List or create clients (`target_weight`, `target_adherence` optional) |
| GET | `/api/clients/<name>` | Client detail |
| GET | `/api/clients/<name>/membership` | Membership status |
| GET / POST | `/api/clients/<name>/progress` | `{"week": "W1", "adherence": 85}` |
| GET / POST | `/api/clients/<name>/workouts` | `{"workout_type": "Strength", "duration_min": 45}` |
| GET / POST | `/api/clients/<name>/workouts/<id>/exercises` | `{"name": "Squat", "sets": 5, "reps": 5, "weight": 100}` |
| GET / POST | `/api/clients/<name>/metrics` | `{"weight": 80, "waist": 90, "bodyfat": 20}` |
| POST | `/api/clients/<name>/generate-program` | Trainer/Admin token required; `{"goal": "MG"}` optional |
| GET | `/api/clients/<name>/report.pdf` | PDF client report |
| POST | `/api/login` | `{"username": "admin", "password": "..."}` → `{"token": ...}` |
| GET | `/api/me` | Current user (token required) |
| GET / POST | `/api/users` | List or create users (Admin token required) |

Example:

```bash
curl -X POST localhost:5000/api/clients -H "Content-Type: application/json" \
     -d '{"name": "Arjun", "weight": 80, "program": "FL"}'
TOKEN=$(curl -s -X POST localhost:5000/api/login -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "change-me"}' | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -X POST localhost:5000/api/clients/Arjun/generate-program -H "Authorization: Bearer $TOKEN"
curl -o arjun.pdf localhost:5000/api/clients/Arjun/report.pdf
```

## CI/CD Pipeline

```
 git push / pull request / tag
          │
          ├────► GitHub Actions (.github/workflows/main.yml)
          │        Build & Lint (compileall, flake8, shellcheck) → Docker build → Pytest in container
          │        → smoke test → on tags v*: push image to Docker Hub
          │
          └────► Jenkins (Jenkinsfile, polls GitHub every 5 min)
                   Checkout → clean venv → lint → unit tests (JUnit + coverage)
                   → SonarQube analysis → Quality Gate (pipeline aborts if it fails)
                   → Docker build → Pytest inside the container → push to Docker Hub
                   → build artifacts → deploy to Kubernetes (chosen strategy)
                   → smoke test → automatic rollback if anything fails
```

Every build produces an image tagged `<version>-b<build>` (immutable, used for deployments), `<version>`, `latest`, and the git tag if the commit is tagged. Jenkins archives the JUnit report, coverage XML, SonarQube quality gate and measures, a source tarball and a build-info file per build.

### Jenkins Setup

A complete walkthrough for a fresh Ubuntu VM (Docker, Minikube, SonarQube, Jenkins, every strategy, and the screenshots to take) is in [docs/BITS_VM_GUIDE.md](docs/BITS_VM_GUIDE.md).


1. Plugins: **Pipeline**, **Git**, **JUnit**, **Credentials Binding**, **SonarQube Scanner**. The agent needs `python3`, `docker` and `kubectl` (add the `jenkins` user to the `docker` group).
2. *Manage Jenkins → Tools*: add a SonarQube Scanner installation named `SonarScanner` (install automatically).
3. *Manage Jenkins → System*: add a SonarQube server named `SonarQube` with its URL and a token credential.
4. *Manage Jenkins → Credentials*: add
   - `dockerhub-creds` — *Username with password*: Docker Hub username and an access token
   - `kubeconfig` — *Secret file*: the kubeconfig of the cluster (for Minikube, `minikube kubectl -- config view --flatten --minify`)
5. Create a **Pipeline** job → *Pipeline script from SCM* → Git → this repository → branch `*/main` → script path `Jenkinsfile`. Set `DEFAULT_DOCKERHUB_USER` at the top of the Jenkinsfile (or the `DOCKERHUB_USER` parameter).
6. Run *Build Now* once so Jenkins learns the parameters. Builds triggered by polling deploy with the rolling strategy; *Build with Parameters* lets you pick another strategy, a baseline image for canary / A-B / shadow, the canary weight, or simulate a bad release to see the automatic rollback.

### SonarQube

```bash
docker run -d --name sonarqube -p 9000:9000 sonarqube:lts-community   # http://localhost:9000, admin/admin
```

Create the project `aceest-fitness` and a token, and add a webhook *Administration → Configuration → Webhooks* to `http://<jenkins-host>/sonarqube-webhook/` so the Quality Gate stage gets the result. The analysis settings (sources, tests, exclusions, coverage and JUnit report paths) are in [sonar-project.properties](sonar-project.properties). To run an analysis without Jenkins:

```bash
pytest --junitxml=reports/junit.xml --cov --cov-report=xml:reports/coverage.xml
docker run --rm --network host -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli \
    -Dsonar.host.url=http://localhost:9000 -Dsonar.token=<token>
```

### Docker Hub

Images are published to `<dockerhub-user>/aceest-fitness` by Jenkins on every build, and by GitHub Actions when a `v*` tag is pushed (repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`). To publish all released versions by hand:

```bash
for v in 1.0.0 1.1.0 2.0.0; do
  git checkout "v$v"
  docker build --build-arg APP_VERSION=$v -t <dockerhub-user>/aceest-fitness:$v .
  docker push <dockerhub-user>/aceest-fitness:$v
done
git checkout main
```

## Kubernetes Deployment

Each strategy runs in its own namespace and is exposed by the NGINX ingress controller under its own path, so all five can run on one cluster at the same time:

| Strategy | Namespace | URL | How it works | Rollback |
|---|---|---|---|---|
| Rolling update | `aceest-rolling` | `/rolling/` | 4 replicas, `maxSurge: 1`, `maxUnavailable: 0`: pods replaced one at a time, no downtime | `kubectl rollout undo` |
| Blue-green | `aceest-blue-green` | `/blue-green/` | New version goes to the idle colour, is smoke-tested through its preview service, then the live Service selector is switched | Switch the selector back (old colour still running) |
| Canary | `aceest-canary` | `/canary/` | Stable (3 pods) + canary (1 pod); ingress `canary-weight` sends `CANARY_WEIGHT`% (default 20) of requests to the canary | Remove the canary ingress, scale canary to 0 |
| A/B testing | `aceest-ab` | `/ab/` | Requests with header `X-User-Group: B` (or cookie `ab_group=always`) go to variant B, everyone else to A | Remove the B ingress, scale B to 0 |
| Shadow | `aceest-shadow` | `/shadow/` | An nginx proxy serves users from the primary and mirrors every request to the shadow; shadow responses are discarded and it has its own throwaway database | Scale shadow to 0 |

```
k8s/
├── base/            namespace, ConfigMap (ACEEST_DB), PersistentVolumeClaim (rendered per namespace)
├── rolling/         deployment, service, ingress
├── blue-green/      blue + green deployments, live service, preview services, ingress
├── canary/          stable + canary deployments/services, main ingress, canary ingress (weight)
├── ab-testing/      variant A + B deployments/services, ingress A, ingress B (header/cookie)
├── shadow/          primary + shadow deployments/services, nginx mirror proxy, ingress
└── scripts/
    ├── deploy.sh      deploy an image with a strategy
    ├── smoke-test.sh  /health and /version checks from inside the cluster
    ├── rollback.sh    return a strategy to its last stable version
    ├── promote.sh     make the new version the only one (canary, A/B, shadow, blue-green)
    ├── traffic.sh     send N requests and count which version answered
    └── status.sh      what is running for each strategy
```

All app pods have readiness and liveness probes on `/health`, CPU/memory requests and limits, run as non-root without privilege escalation, and read the admin password and token key from a per-namespace Secret created on first deploy. Data is SQLite on a PersistentVolumeClaim shared by the live tracks of a strategy; this works on single-node Minikube (`ReadWriteOnce`), while a multi-node cloud cluster would need `ReadWriteMany` storage or a database server.

### Running it on Minikube

```bash
minikube start --cpus=4 --memory=6144 --addons=ingress
IMAGE=<dockerhub-user>/aceest-fitness

k8s/scripts/deploy.sh rolling    $IMAGE:2.0.0
k8s/scripts/deploy.sh blue-green $IMAGE:1.1.0      # first deploy: blue is live
k8s/scripts/deploy.sh blue-green $IMAGE:2.0.0      # green gets 2.0.0, then traffic switches
k8s/scripts/deploy.sh canary     $IMAGE:2.0.0 $IMAGE:1.1.0   # stable 1.1.0, canary 2.0.0
k8s/scripts/deploy.sh ab-testing $IMAGE:2.0.0 $IMAGE:1.1.0   # A = 1.1.0, B = 2.0.0
k8s/scripts/deploy.sh shadow     $IMAGE:2.0.0 $IMAGE:1.1.0   # users on 1.1.0, copy to 2.0.0

k8s/scripts/smoke-test.sh canary 2.0.0
k8s/scripts/status.sh
```

Reach the ingress with `minikube ip` (Linux) or `minikube tunnel` (macOS / Windows, then use `http://127.0.0.1`):

```bash
URL=http://$(minikube ip)          # or http://127.0.0.1 with minikube tunnel
curl $URL/rolling/version
k8s/scripts/traffic.sh $URL canary 50                       # about 80% 1.1.0 / 20% 2.0.0
k8s/scripts/traffic.sh $URL ab 10 -H 'X-User-Group: B'      # all 2.0.0
k8s/scripts/traffic.sh $URL ab 10                           # all 1.1.0
kubectl -n aceest-shadow logs deploy/aceest-shadow          # mirrored requests arrive here
```

Promote or roll back:

```bash
k8s/scripts/promote.sh canary        # stable becomes 2.0.0, canary retired
k8s/scripts/rollback.sh blue-green   # live traffic back to the previous colour
k8s/scripts/rollback.sh rolling      # kubectl rollout undo
```

For a public endpoint URL, expose the ingress controller with a cloud LoadBalancer (EKS, AKS, GKE: the same manifests and scripts work there) or tunnel the Minikube ingress, for example `ngrok http 80` alongside `minikube tunnel`.

## Branching and Versioning

- `main` — always releasable; changes arrive through pull requests merged with `--no-ff`
- `feature/<name>`, `fix/<name>`, `test/<name>`, `ci/<name>`, `docs/<name>` — work branches
- Releases are tagged `vMAJOR.MINOR.PATCH` (`v1.0.0` Assignment 1 baseline, `v1.1.0` version endpoint, `v2.0.0` v3.x feature port + full pipeline); the `VERSION` file holds the current version

Commit messages follow the `type: summary` style, e.g. `feat: add BMI endpoint`, `test: cover membership expiry`, `ci: run pytest inside docker`.
