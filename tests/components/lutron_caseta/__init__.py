"""Tests for the Lutron Caseta integration."""


from unittest.mock import patch

from homeassistant.components.lutron_caseta import DOMAIN
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
)
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

ENTRY_MOCK_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_KEYFILE: "",
    CONF_CERTFILE: "",
    CONF_CA_CERTS: "",
}


async def async_setup_integration(hass, mock_bridge) -> MockConfigEntry:
    """Set up a mock bridge."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_MOCK_DATA)
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls"
    ) as create_tls:
        create_tls.return_value = mock_bridge(can_connect=True)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    return mock_entry


class MockBridge:
    """Mock Lutron bridge that emulates configured connected status."""

    def __init__(self, can_connect=True):
        """Initialize MockBridge instance with configured mock connectivity."""
        self.can_connect = can_connect
        self.is_currently_connected = False
        self.buttons = {}
        self.areas = {}
        self.occupancy_groups = {}
        self.scenes = self.get_scenes()
        self.devices = self.get_devices()

    async def connect(self):
        """Connect the mock bridge."""
        if self.can_connect:
            self.is_currently_connected = True

    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self.is_currently_connected

    def get_devices(self):
        """Return devices on the bridge."""
        return {
            "1": {"serial": 1234, "name": "bridge", "model": "model", "type": "type"}
        }

    def get_devices_by_domain(self, domain):
        """Return devices on the bridge."""
        return {}

    def get_scenes(self):
        """Return scenes on the bridge."""
        return {}

    async def close(self):
        """Close the mock bridge connection."""
        self.is_currently_connected = False
