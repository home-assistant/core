"""Test the coordinator."""

from unittest.mock import MagicMock

from guntamatic.heater import NoSerialException
import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "side_effect",
    [
        requests.exceptions.ConnectionError("Connection lost"),
        NoSerialException,
        Exception("Unknown error"),
    ],
)
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    side_effect: Exception,
) -> None:
    """Test coordinator handles update failures."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_heater.return_value.parse_data.side_effect = side_effect
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.guntamatic_heater_boiler_temperature")
    assert state.state == STATE_UNAVAILABLE
