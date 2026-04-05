"""Test the coordinator."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test coordinator handles update failure."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_heater.return_value.get_data.side_effect = Exception("Connection lost")
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.guntamatic_heater_boiler_temperature")
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test coordinator handles empty data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_heater.return_value.get_data.return_value = {}
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.guntamatic_heater_boiler_temperature")
    assert state.state == STATE_UNAVAILABLE
