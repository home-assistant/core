"""Test the Fronius integration."""
from homeassistant.components.fronius.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from . import mock_responses, setup_fronius_integration


async def test_unload_config_entry(hass, aioclient_mock):
    """Test that configuration entry supports unloading."""
    mock_responses(aioclient_mock)
    await setup_fronius_integration(hass)

    fronius_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(fronius_entries) == 1

    test_entry = fronius_entries[0]
    assert test_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(test_entry.entry_id)
    await hass.async_block_till_done()

    assert test_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
