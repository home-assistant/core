"""Test the Whirlpool Sixth Sense init."""
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from homeassistant.components.whirlpool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.components.whirlpool import init_integration


async def test_setup(hass: HomeAssistant):
    """Test setup."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_http_exception(hass: HomeAssistant, mock_auth_api: MagicMock):
    """Test setup with an http exception."""
    mock_auth_api.return_value.do_auth = AsyncMock(
        side_effect=aiohttp.ClientConnectionError()
    )
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(hass: HomeAssistant, mock_auth_api: MagicMock):
    """Test setup with failed auth."""
    mock_auth_api.return_value.do_auth = AsyncMock()
    mock_auth_api.return_value.is_access_token_valid.return_value = False
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_fetch_appliances_failed(
    hass: HomeAssistant, mock_appliances_manager_api: MagicMock
):
    """Test setup with failed fetch_appliances."""
    mock_appliances_manager_api.return_value.fetch_appliances.return_value = False
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant):
    """Test successful unload of entry."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
