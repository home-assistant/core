"""Tests for the ATAG integration."""

from spencerassistant.components.atag import DOMAIN
from spencerassistant.config_entries import ConfigEntryState
from spencerassistant.core import spencerAssistant

from . import init_integration, mock_connection

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: spencerAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test configuration entry not ready on library error."""
    mock_connection(aioclient_mock, conn_error=True)
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: spencerAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the ATAG configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)
