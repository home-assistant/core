"""Tests for myuplink sensor module."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor state."""
    await setup_integration(hass, mock_config_entry)
    # await hass.async_block_till_done()

    state = hass.states.get("sensor.f730_cu_3x400v_average_outdoor_temp_bt1")
    state = hass.states.get("sensor.f730_cu_3x400v_current_be1")
    assert state is not None
    assert state.state == "3.1"
