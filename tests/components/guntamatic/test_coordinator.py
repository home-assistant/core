"""Test the coordinator."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import requests

from homeassistant.components.guntamatic.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .conftest import MOCK_PARSE_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator raises UpdateFailed on connection error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_heater.parse_data.side_effect = (
        requests.exceptions.ConnectionError("Connection lost"),
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.last_update_success is False


async def test_coordinator_returns_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator returns correct data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.last_update_success is True
    assert mock_config_entry.runtime_data.data == MOCK_PARSE_DATA
