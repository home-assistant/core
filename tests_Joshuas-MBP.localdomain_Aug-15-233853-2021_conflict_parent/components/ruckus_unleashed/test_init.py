"""Test the Ruckus Unleashed config flow."""
from unittest.mock import patch

from pyruckus.exceptions import AuthenticationError

from homeassistant.components.ruckus_unleashed import (
    API_AP,
    API_DEVICE_NAME,
    API_ID,
    API_MAC,
    API_MODEL,
    API_SYSTEM_OVERVIEW,
    API_VERSION,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from tests.components.ruckus_unleashed import (
    DEFAULT_AP_INFO,
    DEFAULT_SYSTEM_INFO,
    DEFAULT_TITLE,
    init_integration,
    mock_config_entry,
)


async def test_setup_entry_login_error(hass):
    """Test entry setup failed due to login error."""
    entry = mock_config_entry()
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus",
        side_effect=AuthenticationError,
    ):
        entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_setup_entry_connection_error(hass):
    """Test entry setup failed due to connection error."""
    entry = mock_config_entry()
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus",
        side_effect=ConnectionError,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_router_device_setup(hass):
    """Test a router device is created."""
    await init_integration(hass)

    device_info = DEFAULT_AP_INFO[API_AP][API_ID]["1"]

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(
        identifiers={(CONNECTION_NETWORK_MAC, device_info[API_MAC])},
        connections={(CONNECTION_NETWORK_MAC, device_info[API_MAC])},
    )

    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.model == device_info[API_MODEL]
    assert device.name == device_info[API_DEVICE_NAME]
    assert device.sw_version == DEFAULT_SYSTEM_INFO[API_SYSTEM_OVERVIEW][API_VERSION]
    assert device.via_device_id is None


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_config_not_ready_during_setup(hass):
    """Test we throw a ConfigNotReady if Coordinator update fails."""
    entry = mock_config_entry()
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        return_value=None,
    ), patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.mesh_name",
        return_value=DEFAULT_TITLE,
    ), patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.system_info",
        return_value=DEFAULT_SYSTEM_INFO,
    ), patch(
        "homeassistant.components.ruckus_unleashed.RuckusUnleashedDataUpdateCoordinator._async_update_data",
        side_effect=ConnectionError,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_SETUP_RETRY
