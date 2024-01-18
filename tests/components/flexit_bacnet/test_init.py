"""Tests for the Flexit Nordic (BACnet) __init__."""
from homeassistant.components.flexit_bacnet.const import DOMAIN as FLEXIT_BACNET_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.flexit_bacnet import setup_with_selected_platforms


async def test_loading_and_unloading_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_flexit_bacnet
) -> None:
    """Test loading and unloading a config entry."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert len(hass.config_entries.async_entries(FLEXIT_BACNET_DOMAIN)) == 1
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(FLEXIT_BACNET_DOMAIN)
