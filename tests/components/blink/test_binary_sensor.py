"""Test the Blink binary sensor platform."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import CAMERA_ATTRIBUTES


@pytest.mark.parametrize(
    ("battery", "expected_state"),
    [
        ("ok", STATE_OFF),
        ("low", STATE_ON),
        (None, STATE_UNKNOWN),
    ],
)
async def test_battery_binary_sensor(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    camera: MagicMock,
    battery: str | None,
    expected_state: str,
) -> None:
    """Test the battery state, including wired cameras reporting no battery."""
    camera.attributes = {**CAMERA_ATTRIBUTES, "battery": battery}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.camera_1_battery")
    assert state is not None
    assert state.state == expected_state
