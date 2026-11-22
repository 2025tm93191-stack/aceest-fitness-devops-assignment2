"""Training program catalogue, ported from the ACEest v1.x desktop scripts."""

import secrets

PROGRAMS = {
    "FL": {
        "name": "Fat Loss",
        "workout": [
            "Mon: Back Squat 5x5 + Core",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: Deadlift + Box Jumps",
            "Fri: Zone 2 Cardio 30min",
        ],
        "diet": [
            "Breakfast: Egg Whites + Oats",
            "Lunch: Grilled Chicken + Brown Rice",
            "Dinner: Fish Curry + Millet Roti",
        ],
        "calorie_factor": 22,
    },
    "MG": {
        "name": "Muscle Gain",
        "workout": [
            "Mon: Squat 5x5",
            "Tue: Bench 5x5",
            "Wed: Deadlift 4x6",
            "Thu: Front Squat 4x8",
            "Fri: Incline Press 4x10",
            "Sat: Barbell Rows 4x10",
        ],
        "diet": [
            "Breakfast: Eggs + Peanut Butter Oats",
            "Lunch: Chicken Biryani",
            "Dinner: Mutton Curry + Rice",
        ],
        "calorie_factor": 35,
    },
    "BG": {
        "name": "Beginner",
        "workout": [
            "Full Body Circuit: Air Squats, Ring Rows, Push-ups",
            "Focus: Technique & Consistency",
        ],
        "diet": [
            "Balanced Tamil Meals: Idli / Dosa / Rice + Dal",
            "Protein Target: 120g/day",
        ],
        "calorie_factor": 26,
    },
}


def list_programs():
    """Return a lightweight summary of every program."""
    return [{"code": code, "name": p["name"]} for code, p in PROGRAMS.items()]


def get_program(code):
    """Look up a program by its code (case-insensitive). Returns None if unknown."""
    if not isinstance(code, str):
        return None
    key = code.strip().upper()
    program = PROGRAMS.get(key)
    if program is None:
        return None
    return {"code": key, **program}


# Templates used by the "AI-style program generator" in ACEest v3.1.2 / v3.2.4.
PLAN_TEMPLATES = {
    "FL": ["Full Body HIIT", "Circuit Training", "Cardio + Weights"],
    "MG": ["Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"],
    "BG": ["Full Body 3x/week", "Light Strength + Mobility"],
}


def generate_plan(goal=None, chooser=secrets.choice):
    """Pick a training split for a goal (program code); a random goal if none is given.

    Returns (goal_code, plan). Raises ValueError for an unknown goal.
    """
    if goal is None:
        goal = chooser(sorted(PLAN_TEMPLATES))
    key = str(goal).strip().upper()
    if key not in PLAN_TEMPLATES:
        raise ValueError(f"Unknown program '{goal}'")
    return key, chooser(PLAN_TEMPLATES[key])
