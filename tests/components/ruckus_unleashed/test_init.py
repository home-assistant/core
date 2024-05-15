"""Test the Ruckus Unleashed config flow."""

from unittest.mock import AsyncMock

from aioruckus.const import ERROR_CONNECT_TIMEOUT, ERROR_LOGIN_INCORRECT
from aioruckus.exceptions import AuthenticationError

from homeassistant.components.ruckus_unleashed import DOMAIN, MANUFACTURER
from homeassistant.components.ruckus_unleashed.const import (
    API_AP_DEVNAME,
    API_AP_MAC,
    API_AP_MODEL,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_VERSION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from . import (
    DEFAULT_AP_INFO,
    DEFAULT_SYSTEM_INFO,
    RuckusAjaxApiPatchContext,
    init_integration,
    mock_config_entry,
)


async def test_setup_entry_login_error(hass: HomeAssistant) -> None:
    """Test entry setup failed due to login error."""
    entry = mock_config_entry()
    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=AuthenticationError(ERROR_LOGIN_INCORRECT))
    ):
        entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test entry setup failed due to connection error."""
    entry = mock_config_entry()
    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=ConnectionError(ERROR_CONNECT_TIMEOUT))
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_router_device_setup(hass: HomeAssistant) -> None:
    """Test a router device is created."""
    await init_integration(hass)

    device_info = DEFAULT_AP_INFO[0]

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(CONNECTION_NETWORK_MAC, device_info[API_AP_MAC])},
        connections={(CONNECTION_NETWORK_MAC, device_info[API_AP_MAC])},
    )

    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.model == device_info[API_AP_MODEL]
    assert device.name == device_info[API_AP_DEVNAME]
    assert (
        device.sw_version
        == DEFAULT_SYSTEM_INFO[API_SYS_SYSINFO][API_SYS_SYSINFO_VERSION]
    )
    assert device.via_device_id is None


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    with RuckusAjaxApiPatchContext():
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
