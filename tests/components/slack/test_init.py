"""Test Slack integration."""

from homeassistant.components.slack.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CONF_DATA, async_init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test Slack setup."""
    entry: ConfigEntry = await async_init_integration(hass, aioclient_mock)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry: ConfigEntry = await async_init_integration(
        hass, aioclient_mock, error="cannot_connect"
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid auth during setup."""
    entry: ConfigEntry = await async_init_integration(
        hass, aioclient_mock, error="invalid_auth"
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
