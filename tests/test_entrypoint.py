import ACEest_Fitness
import app as app_module


def test_entrypoint_exposes_the_app():
    assert ACEest_Fitness.app is app_module.app
    assert ACEest_Fitness.create_app is app_module.create_app
