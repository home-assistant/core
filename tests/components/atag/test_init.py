"""Tests for the ATAG integration."""
import aiohttp

from homeassistant.components.atag import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_SETUP_RETRY
from homeassistant.core import HomeAssistant

from tests.async_mock import patch
from tests.components.atag import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test configuration entry not ready on library error."""
    aioclient_mock.get("http://127.0.0.1:10000/retrieve", exc=aiohttp.ClientError)
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_config_entry_empty_reply(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test configuration entry not ready when library returns False."""
    with patch("pyatag.AtagOne.update", return_value=False):
        entry = await init_integration(hass, aioclient_mock)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the ATAG configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)
