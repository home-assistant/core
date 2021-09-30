"""Tests for the DirecTV integration."""
from homeassistant.components.directv.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.components.directv import setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker

# pylint: disable=redefined-outer-name


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the DirecTV configuration entry not ready."""
    entry = await setup_integration(hass, aioclient_mock, setup_error=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the DirecTV configuration entry unloading."""
    entry = await setup_integration(hass, aioclient_mock)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED
