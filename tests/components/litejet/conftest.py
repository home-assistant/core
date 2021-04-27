"""Fixtures for LiteJet testing."""
from datetime import timedelta
from unittest.mock import patch

import pytest

import homeassistant.util.dt as dt_util


@pytest.fixture
def mock_litejet():
    """Mock LiteJet system."""
    with patch("pylitejet.LiteJet") as mock_pylitejet:

        def get_load_name(number):
            return f"Mock Load #{number}"

        def get_scene_name(number):
            return f"Mock Scene #{number}"

        def get_switch_name(number):
            return f"Mock Switch #{number}"

        mock_lj = mock_pylitejet.return_value

        mock_lj.switch_pressed_callbacks = {}
        mock_lj.switch_released_callbacks = {}
        mock_lj.load_activated_callbacks = {}
        mock_lj.load_deactivated_callbacks = {}

        def on_switch_pressed(number, callback):
            mock_lj.switch_pressed_callbacks[number] = callback

        def on_switch_released(number, callback):
            mock_lj.switch_released_callbacks[number] = callback

        def on_load_activated(number, callback):
            mock_lj.load_activated_callbacks[number] = callback

        def on_load_deactivated(number, callback):
            mock_lj.load_deactivated_callbacks[number] = callback

        mock_lj.on_switch_pressed.side_effect = on_switch_pressed
        mock_lj.on_switch_released.side_effect = on_switch_released
        mock_lj.on_load_activated.side_effect = on_load_activated
        mock_lj.on_load_deactivated.side_effect = on_load_deactivated

        mock_lj.loads.return_value = range(1, 3)
        mock_lj.get_load_name.side_effect = get_load_name
        mock_lj.get_load_level.return_value = 0

        mock_lj.button_switches.return_value = range(1, 3)
        mock_lj.all_switches.return_value = range(1, 6)
        mock_lj.get_switch_name.side_effect = get_switch_name

        mock_lj.scenes.return_value = range(1, 3)
        mock_lj.get_scene_name.side_effect = get_scene_name

        mock_lj.start_time = dt_util.utcnow()
        mock_lj.last_delta = timedelta(0)

        yield mock_lj
