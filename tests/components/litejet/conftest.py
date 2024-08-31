"""Fixtures for LiteJet testing."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

import homeassistant.util.dt as dt_util


@pytest.fixture
def mock_litejet():
    """Mock LiteJet system."""
    with patch("pylitejet.LiteJet") as mock_pylitejet:

        async def get_load_name(number):
            return f"Mock Load #{number}"

        async def get_scene_name(number):
            return f"Mock Scene #{number}"

        async def get_switch_name(number):
            return f"Mock Switch #{number}"

        def get_switch_keypad_number(number):
            return number + 100

        def get_switch_keypad_name(number):
            return f"Mock Keypad #{number + 100}"

        mock_lj = mock_pylitejet.return_value

        mock_lj.switch_pressed_callbacks = {}
        mock_lj.switch_released_callbacks = {}
        mock_lj.load_activated_callbacks = {}
        mock_lj.load_deactivated_callbacks = {}
        mock_lj.connected_changed_callbacks = []

        def on_switch_pressed(number, callback):
            mock_lj.switch_pressed_callbacks[number] = callback

        def on_switch_released(number, callback):
            mock_lj.switch_released_callbacks[number] = callback

        def on_load_activated(number, callback):
            mock_lj.load_activated_callbacks[number] = callback

        def on_load_deactivated(number, callback):
            mock_lj.load_deactivated_callbacks[number] = callback

        def on_connected_changed(callback):
            mock_lj.connected_changed_callbacks.append(callback)

        mock_lj.on_switch_pressed.side_effect = on_switch_pressed
        mock_lj.on_switch_released.side_effect = on_switch_released
        mock_lj.on_load_activated.side_effect = on_load_activated
        mock_lj.on_load_deactivated.side_effect = on_load_deactivated
        mock_lj.on_connected_changed.side_effect = on_connected_changed

        mock_lj.open = AsyncMock()
        mock_lj.close = AsyncMock()

        mock_lj.loads.return_value = range(1, 3)
        mock_lj.get_load_name = AsyncMock(side_effect=get_load_name)
        mock_lj.get_load_level = AsyncMock(return_value=0)
        mock_lj.activate_load = AsyncMock()
        mock_lj.activate_load_at = AsyncMock()
        mock_lj.deactivate_load = AsyncMock()

        mock_lj.button_switches.return_value = range(1, 3)
        mock_lj.all_switches.return_value = range(1, 6)
        mock_lj.get_switch_name = AsyncMock(side_effect=get_switch_name)
        mock_lj.press_switch = AsyncMock()
        mock_lj.release_switch = AsyncMock()
        mock_lj.get_switch_keypad_number = Mock(side_effect=get_switch_keypad_number)
        mock_lj.get_switch_keypad_name = Mock(side_effect=get_switch_keypad_name)

        mock_lj.scenes.return_value = range(1, 3)
        mock_lj.get_scene_name = AsyncMock(side_effect=get_scene_name)
        mock_lj.activate_scene = AsyncMock()
        mock_lj.deactivate_scene = AsyncMock()

        mock_lj.start_time = dt_util.utcnow()
        mock_lj.last_delta = timedelta(0)
        mock_lj.connected = True
        mock_lj.model_name = "MockJet"

        def connected_changed(connected: bool, reason: str) -> None:
            mock_lj.connected = connected
            for callback in mock_lj.connected_changed_callbacks:
                callback(connected, reason)

        mock_lj.connected_changed = connected_changed

        yield mock_lj
