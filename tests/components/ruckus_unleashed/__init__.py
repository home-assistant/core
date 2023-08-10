"""Tests for the Ruckus Unleashed integration."""
from unittest.mock import patch

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
from homeassistant.helpers import device_registry as dr

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
    entry.add_to_hass(hass)
    # Make device tied to other integration so device tracker entities get enabled
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        name="Device from other integration",
        config_entry_id=other_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, TEST_CLIENT[API_MAC])},
    )
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
        "homeassistant.components.ruckus_unleashed.Ruckus.ap_info",
        return_value=DEFAULT_AP_INFO,
    ), patch(
        "homeassistant.components.ruckus_unleashed.RuckusUnleashedDataUpdateCoordinator._fetch_clients",
        return_value={
            TEST_CLIENT[API_MAC]: TEST_CLIENT,
        },
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
