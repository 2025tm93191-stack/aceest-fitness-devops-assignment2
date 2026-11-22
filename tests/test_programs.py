import pytest

from fitness.programs import PLAN_TEMPLATES, PROGRAMS, generate_plan, get_program, list_programs


def test_all_three_programs_exist():
    assert set(PROGRAMS) == {"FL", "MG", "BG"}


def test_every_program_has_required_fields():
    for program in PROGRAMS.values():
        assert program["name"]
        assert program["workout"] and program["diet"]
        assert program["calorie_factor"] > 0


def test_list_programs_summary():
    assert {"code": "FL", "name": "Fat Loss"} in list_programs()


def test_get_program_is_case_insensitive():
    assert get_program(" mg ")["name"] == "Muscle Gain"


def test_get_program_unknown_returns_none():
    assert get_program("ZZ") is None
    assert get_program(None) is None


def test_generate_plan_for_goal():
    goal, plan = generate_plan("mg", chooser=lambda options: options[0])
    assert (goal, plan) == ("MG", PLAN_TEMPLATES["MG"][0])


def test_generate_plan_random_goal_and_unknown():
    goal, plan = generate_plan()
    assert plan in PLAN_TEMPLATES[goal]
    with pytest.raises(ValueError):
        generate_plan("XX")


def test_plan_templates_cover_every_program():
    assert set(PLAN_TEMPLATES) == set(PROGRAMS)
