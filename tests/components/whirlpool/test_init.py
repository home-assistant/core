"""Test the Whirlpool Sixth Sense init."""
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from whirlpool.backendselector import Brand, Region

from homeassistant.components.whirlpool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import init_integration, init_integration_with_entry

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_backend_selector_api: MagicMock,
    region,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test setup."""
    entry = await init_integration(hass, region[0])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_backend_selector_api.assert_called_once_with(region[2], region[1])


async def test_setup_region_fallback(
    hass: HomeAssistant,
    mock_backend_selector_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test setup when no region is available on the ConfigEntry.

    This can happen after a version update, since there was no region in the first versions.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
        },
    )
    entry = await init_integration_with_entry(hass, entry)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_backend_selector_api.assert_called_once_with(Brand.Whirlpool, Region.EU)


async def test_setup_http_exception(
    hass: HomeAssistant,
    mock_auth_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test setup with an http exception."""
    mock_auth_api.return_value.do_auth = AsyncMock(
        side_effect=aiohttp.ClientConnectionError()
    )
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(
    hass: HomeAssistant,
    mock_auth_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test setup with failed auth."""
    mock_auth_api.return_value.do_auth = AsyncMock()
    mock_auth_api.return_value.is_access_token_valid.return_value = False
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_fetch_appliances_failed(
    hass: HomeAssistant,
    mock_appliances_manager_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
) -> None:
    """Test setup with failed fetch_appliances."""
    mock_appliances_manager_api.return_value.fetch_appliances.return_value = False
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_aircon_api_instances: MagicMock,
    mock_sensor_api_instances: MagicMock,
) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
