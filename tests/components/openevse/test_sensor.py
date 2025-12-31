"""Tests for the OpenEVSE sensor platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test setting up the sensor platform."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.charging_status")
    assert state.state == "Charging"

    state = hass.states.get("sensor.charge_time_elapsed")
    assert state.state == "60.0"

    state = hass.states.get("sensor.ambient_temperature")
    assert state.state == "25.5"

    state = hass.states.get("sensor.usage_this_session")
    assert state.state == "15.0"

    state = hass.states.get("sensor.total_usage")
    assert state.state == "500.0"
