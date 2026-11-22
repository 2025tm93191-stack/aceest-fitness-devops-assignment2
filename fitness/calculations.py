"""Pure calculation helpers, kept free of Flask/DB code so they are easy to unit test."""

from .programs import PROGRAMS


def _positive_number(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number


def estimate_calories(weight_kg, program_code):
    """Daily calorie target = body weight (kg) x the program's calorie factor."""
    weight = _positive_number(weight_kg, "weight_kg")
    program = PROGRAMS.get(str(program_code).strip().upper())
    if program is None:
        raise ValueError(f"Unknown program '{program_code}'")
    return int(weight * program["calorie_factor"])


def calculate_bmi(height_cm, weight_kg):
    """Return (bmi, category) using WHO adult categories."""
    height_m = _positive_number(height_cm, "height_cm") / 100
    weight = _positive_number(weight_kg, "weight_kg")
    bmi = round(weight / (height_m ** 2), 1)
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    return bmi, category


def validate_adherence(value):
    """Weekly adherence is a whole-number percentage between 0 and 100."""
    if isinstance(value, bool):
        raise ValueError("adherence must be an integer")
    try:
        adherence = int(value)
    except (TypeError, ValueError):
        raise ValueError("adherence must be an integer")
    if not 0 <= adherence <= 100:
        raise ValueError("adherence must be between 0 and 100")
    return adherence


def positive_int(value, field):
    """A whole number greater than zero (booleans and floats are rejected)."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def optional_number(value, field, low=0.0, high=None):
    """None stays None; otherwise a number in (low, high)."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    if number <= low or (high is not None and number >= high):
        limit = f"between {low:g} and {high:g}" if high is not None else f"greater than {low:g}"
        raise ValueError(f"{field} must be {limit}")
    return number


def validate_metrics(data):
    """Body metrics from ACEest v2.2.4: weight is required, waist and body fat are optional."""
    return {
        "weight": _positive_number(data.get("weight"), "weight"),
        "waist": optional_number(data.get("waist"), "waist"),
        "bodyfat": optional_number(data.get("bodyfat"), "bodyfat", high=100),
    }


def validate_exercise(data):
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("name is required")
    weight = data.get("weight")  # None or 0 = bodyweight exercise
    if isinstance(weight, bool) or weight not in (None, 0):
        weight = optional_number(weight, "weight")
    return {
        "name": name,
        "sets": positive_int(data.get("sets"), "sets"),
        "reps": positive_int(data.get("reps"), "reps"),
        "weight": weight,
    }
