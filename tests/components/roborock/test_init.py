"""Test for Roborock init."""
from unittest.mock import patch

from homeassistant.components.roborock.const import DOMAIN, VACUUM_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .common import setup_platform


async def test_unload_entry(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test unloading roboorck integration."""
    entry = await setup_platform(hass, VACUUM_DOMAIN)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.async_disconnect"
    ) as mock_disconnect:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_disconnect.call_count == 1
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert not hass.data.get(DOMAIN)


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test that when coordinator update fails, entry retries."""
    with patch(
        "homeassistant.components.roborock.RoborockDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed(),
    ):
        entry = await setup_platform(hass, VACUUM_DOMAIN)
        assert entry.state is ConfigEntryState.SETUP_RETRY
