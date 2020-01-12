"""Tests for the Elgato Key Light integration."""
import aiohttp

from homeassistant.components.elgato.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_SETUP_RETRY
from homeassistant.core import HomeAssistant

from tests.components.elgato import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Elgato Key Light configuration entry not ready."""
    aioclient_mock.get(
        "http://example.local:9123/elgato/accessory-info", exc=aiohttp.ClientError
    )

    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Elgato Key Light configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)
