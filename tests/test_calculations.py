import pytest

from fitness.calculations import (
    calculate_bmi, estimate_calories, optional_number, positive_int, validate_adherence, validate_exercise,
    validate_metrics,
)


@pytest.mark.parametrize("program, expected", [("FL", 1760), ("MG", 2800), ("BG", 2080)])
def test_calories_use_program_factor(program, expected):
    assert estimate_calories(80, program) == expected


def test_calories_accept_lowercase_code_and_numeric_string():
    assert estimate_calories("70", "mg") == 2450


@pytest.mark.parametrize("weight", [0, -5, "abc", None, True])
def test_calories_reject_bad_weight(weight):
    with pytest.raises(ValueError):
        estimate_calories(weight, "FL")


def test_calories_reject_unknown_program():
    with pytest.raises(ValueError, match="Unknown program"):
        estimate_calories(70, "XX")


@pytest.mark.parametrize(
    "height, weight, category",
    [(180, 55, "Underweight"), (175, 70, "Normal"), (170, 80, "Overweight"), (160, 90, "Obese")],
)
def test_bmi_categories(height, weight, category):
    assert calculate_bmi(height, weight)[1] == category


def test_bmi_value_is_rounded():
    assert calculate_bmi(175, 70) == (22.9, "Normal")


def test_bmi_rejects_zero_height():
    with pytest.raises(ValueError):
        calculate_bmi(0, 70)


@pytest.mark.parametrize("value", [0, 50, 100, "75"])
def test_adherence_accepts_valid_range(value):
    assert validate_adherence(value) == int(value)


@pytest.mark.parametrize("value", [-1, 101, "high", None, True])
def test_adherence_rejects_invalid(value):
    with pytest.raises(ValueError):
        validate_adherence(value)


# ---------- v2.0 validators ----------
@pytest.mark.parametrize("value", [0, -1, 2.5, "3", True, None])
def test_positive_int_rejects(value):
    with pytest.raises(ValueError):
        positive_int(value, "sets")


def test_optional_number_bounds():
    assert optional_number(None, "x") is None
    assert optional_number("20.5", "x", high=100) == 20.5
    for bad in (0, 100, "abc", True):
        with pytest.raises(ValueError):
            optional_number(bad, "x", high=100)


def test_validate_metrics_defaults():
    assert validate_metrics({"weight": 70}) == {"weight": 70.0, "waist": None, "bodyfat": None}


def test_validate_exercise_bodyweight_and_errors():
    assert validate_exercise({"name": " Dips ", "sets": 3, "reps": 10, "weight": 0})["name"] == "Dips"
    with pytest.raises(ValueError):
        validate_exercise({"name": "Dips", "sets": 3, "reps": 10, "weight": False})
