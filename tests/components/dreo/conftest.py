"""Test fixtures and helper functions for the Dreo integration tests."""

from unittest.mock import MagicMock, patch

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class ComponentSetup:
    """Helper for setting up the Dreo component."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the setup helper."""
        self.hass = hass
        self.config_entry = MockConfigEntry(
            domain=DOMAIN,
            source=SOURCE_USER,
            data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
            entry_id="test",
        )
        self.config_entry.add_to_hass(hass)

    async def setup(self) -> None:
        """Set up the component."""
        # Mock the client
        mock_client = MagicMock()
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "mode": "auto",
            "speed": 50,
            "oscillate": True,
        }

        # Mock the devices
        mock_devices = [
            {
                "deviceSn": "test-device-id",
                "deviceName": "Test Fan",
                "model": "DR-HTF001S",
                "moduleFirmwareVersion": "1.0.0",
                "mcuFirmwareVersion": "1.0.0",
            }
        ]

        # Create runtime data
        runtime_data = MagicMock()
        runtime_data.client = mock_client
        runtime_data.devices = mock_devices

        # Patch async_login to return runtime data
        with patch(
            "homeassistant.components.dreo.async_login", return_value=runtime_data
        ):
            await self.hass.config_entries.async_setup(self.config_entry.entry_id)
            await self.hass.async_block_till_done()
