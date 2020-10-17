"""Tests for the Ruckus Unleashed integration."""
from homeassistant.components.ruckus_unleashed import DOMAIN
from homeassistant.components.ruckus_unleashed.const import (
    API_ACCESS_POINT,
    API_AP,
    API_DEVICE_NAME,
    API_ID,
    API_IP,
    API_MAC,
    API_MODEL,
    API_NAME,
    API_SERIAL,
    API_SYSTEM_OVERVIEW,
    API_VERSION,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

DEFAULT_TITLE = "Ruckus Mesh"
DEFAULT_UNIQUE_ID = "123456789012"
DEFAULT_SYSTEM_INFO = {
    API_SYSTEM_OVERVIEW: {
        API_SERIAL: DEFAULT_UNIQUE_ID,
        API_VERSION: "v1.0.0",
    }
}
DEFAULT_AP_INFO = {
    API_AP: {
        API_ID: {
            "1": {
                API_MAC: "00:11:22:33:44:55",
                API_DEVICE_NAME: "Test Device",
                API_MODEL: "r510",
            }
        }
    }
}

CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

TEST_CLIENT_ENTITY_ID = "device_tracker.ruckus_test_device"
TEST_CLIENT = {
    API_IP: "1.1.1.2",
    API_MAC: "AA:BB:CC:DD:EE:FF",
    API_NAME: "Ruckus Test Device",
    API_ACCESS_POINT: "00:11:22:33:44:55",
}


def _patch_create(**kwargs):
    """Patch the `Ruckus.create()` method."""
    return patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.create",
        **kwargs,
    )


def _patch_connect(**kwargs):
    """Patch the `Ruckus.connect()` method."""
    if not kwargs:
        kwargs["return_value"] = None
    return patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        **kwargs,
    )


def _patch_mesh_name(**kwargs):
    """Patch the `Ruckus.mesh_name()` method."""
    if not kwargs:
        kwargs["return_value"] = DEFAULT_TITLE
    return patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.mesh_name",
        **kwargs,
    )


def _patch_system_info(**kwargs):
    """Patch the `Ruckus.system_info()` method."""
    if not kwargs:
        kwargs["return_value"] = DEFAULT_SYSTEM_INFO
    return patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.system_info",
        **kwargs,
    )


def _patch_ap_info(**kwargs):
    """Patch the `Ruckus.ap_info()` method."""
    if not kwargs:
        kwargs["return_value"] = DEFAULT_AP_INFO
    return patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.ap_info",
        **kwargs,
    )


def _patch_fetch_clients(**kwargs):
    """Patch the `RuckusUnleashedDataUpdateCoordinator._fetch_clients()` method."""
    if not kwargs:
        kwargs["return_value"] = {
            TEST_CLIENT[API_MAC]: TEST_CLIENT,
        }
    return patch(
        "homeassistant.components.ruckus_unleashed.RuckusUnleashedDataUpdateCoordinator._fetch_clients",
        **kwargs,
    )


def _patch_async_update_data(**kwargs):
    """Patch the `RuckusUnleashedDataUpdateCoordinator._async_update_data()` method."""
    return patch(
        "homeassistant.components.ruckus_unleashed.RuckusUnleashedDataUpdateCoordinator._async_update_data",
        **kwargs,
    )


def mock_config_entry() -> MockConfigEntry:
    """Return a Ruckus Unleashed mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_TITLE,
        unique_id=DEFAULT_UNIQUE_ID,
        data=CONFIG,
        options=None,
    )


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Ruckus Unleashed integration in Home Assistant."""
    entry = mock_config_entry()
    with _patch_connect(), _patch_mesh_name(), _patch_system_info(), _patch_ap_info(), _patch_fetch_clients():
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
