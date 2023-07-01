"""Tests for Glances integration."""
from unittest.mock import MagicMock

from glances_api.exceptions import GlancesApiConnectionError

from homeassistant.components.glances.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that Glances is configured successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED


async def test_conn_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test Glances failed due to connection error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_api.return_value.get_ha_sensor_data.side_effect = GlancesApiConnectionError
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Glances."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
