"""Tests for the Sonsrr integration."""
from homeassistant.components.sonarr.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.core import HomeAssistant

from tests.async_mock import patch
from tests.components.sonarr import setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the configuration entry not ready."""
    entry = await setup_integration(hass, aioclient_mock, connection_error=True)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the configuration entry unloading."""
    with patch(
        "homeassistant.components.sonarr.sensor.async_setup_entry",
        return_value=True,
    ):
        entry = await setup_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_NOT_LOADED
