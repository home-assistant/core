"""Tests for the IPP integration."""
from spencerassistant.components.ipp.const import DOMAIN
from spencerassistant.config_entries import ConfigEntryState
from spencerassistant.core import spencerAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: spencerAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the IPP configuration entry not ready."""
    entry = await init_integration(hass, aioclient_mock, conn_error=True)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: spencerAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the IPP configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED
