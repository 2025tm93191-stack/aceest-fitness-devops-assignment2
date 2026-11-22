"""ACEest Fitness & Gym - application entry point.

The Flask app is built by ``create_app`` in ``app.py``; this module is what Gunicorn serves
(``gunicorn ACEest_Fitness:app``) and what ``python ACEest_Fitness.py`` runs locally.
"""

import os

from app import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
