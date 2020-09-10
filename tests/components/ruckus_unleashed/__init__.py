"""Tests for the Ruckus Unleashed integration."""
from homeassistant.components.ruckus_unleashed import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry

DEFAULT_TITLE = "Ruckus Mesh"

CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

TEST_CLIENT_ENTITY_ID = "device_tracker.ruckus_test_device"
TEST_CLIENT = {
    CONF_IP_ADDRESS: "1.1.1.2",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_NAME: "Ruckus Test Device",
}


def mock_config_entry() -> MockConfigEntry:
    """Return a Ruckus Unleashed mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_TITLE,
        unique_id="1.1.1.1",
        data=CONFIG,
        options=None,
    )


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Ruckus Unleashed integration in Home Assistant."""
    entry = mock_config_entry()
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        return_value=None,
    ), patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.mesh_name",
        return_value=DEFAULT_TITLE,
    ), patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.clients",
        return_value={
            TEST_CLIENT[CONF_MAC]: TEST_CLIENT,
        },
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
