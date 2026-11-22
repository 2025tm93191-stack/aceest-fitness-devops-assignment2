# Legacy ACEest desktop versions

These are the original Tkinter scripts supplied with the assignment, kept unchanged for reference.
They are not part of the Flask application: they are excluded from flake8, SonarQube and the Docker build context.

| Script | Adds | Ported to the Flask app in |
|---|---|---|
| `Aceestver-1.0.py` | Program catalogue (Fat Loss, Muscle Gain, Beginner) with workout and diet plans | `v1.0.0` (`fitness/programs.py`) |
| `Aceestver-1.1.py`, `Aceestver1.1.2.py` | Client form, calorie estimate (weight × factor), CSV export, adherence chart | `v1.0.0` (`/api/clients`, `/api/calories`) |
| `Aceestver2.0.1.py`, `Aceestver-2.1.2.py` (identical) | SQLite storage, clients + weekly progress | `v1.0.0` (`fitness/db.py`, `/api/clients/<name>/progress`) |
| `Aceestver-2.2.1.py` | Progress chart | `v1.0.0` (average adherence in the progress API) |
| `Aceestver-2.2.4.py`, `Aceestver-3.0.1.py` (identical) | Workouts, exercises, body metrics, BMI, membership | `v1.0.0` (workouts, BMI, membership), `v2.0.0` (exercises, metrics, targets) |
| `Aceestver-3.1.2.py` | Login with roles, AI-style program generator, PDF report | `v2.0.0` (`/api/login`, `/api/users`, `/generate-program`, `/report.pdf`) |
| `Aceestver-3.2.4.py` | Consolidated full version of the above | `v2.0.0` |
