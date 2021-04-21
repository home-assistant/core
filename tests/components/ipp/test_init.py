"""Tests for the IPP integration."""
from homeassistant.components.ipp.const import DOMAIN
from homeassistant.config_entries import EntryState
from homeassistant.core import HomeAssistant

from tests.components.ipp import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the IPP configuration entry not ready."""
    entry = await init_integration(hass, aioclient_mock, conn_error=True)
    assert entry.state is EntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the IPP configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is EntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is EntryState.NOT_LOADED
