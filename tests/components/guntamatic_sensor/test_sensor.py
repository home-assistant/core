"""Test the Guntamatic sensors."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test that sensors are created for each data point."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.guntamatic_heater_boiler_temperature")
    assert state is not None
    assert state.state == "14.09"
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_sensor_native_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test sensor returns correct native value."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.guntamatic_heater_outside_temp")
    assert state is not None
    assert state.state == "15.95"
