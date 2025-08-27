"""Debug test to see what devices are created."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_debug_device_creation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Debug test to see what devices are created."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={
            "name": "Living Room",
            "host": "192.168.1.100",
            "port": 80,
            "username": "admin",
            "password": "password123",
        },
        unique_id="ABCD1234567890",
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.amcrest.AmcrestChecker") as mock_api_class:
        mock_api = mock_api_class.return_value

        # Set serial number for device identification
        mock_api.serial_number = MagicMock(return_value="ABCD1234567890")

        mock_api.available = True
        mock_api.async_available_flag.is_set.return_value = True

        # Mock some basic API methods
        mock_api.current_time = "2023-01-01 00:00:00"

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        print(f"Setup result: {result}")

        # List all devices
        devices = device_registry.devices
        print(f"All device IDs: {list(devices.keys())}")

        for device_id, device in devices.items():
            print(
                f"Device {device_id}: identifiers={device.identifiers}, name={device.name}"
            )

        # Check for our specific device
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.entry_id)}
        )
        print(f"Device with config entry ID: {device}")

        device = device_registry.async_get_device(
            identifiers={(DOMAIN, "ABCD1234567890")}
        )
        print(f"Device with serial: {device}")

        # Check entities
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)
        entities = entity_registry.entities
        print(f"All entity IDs: {list(entities.keys())}")

        for entity_id, entity in entities.items():
            print(
                f"Entity {entity_id}: platform={entity.platform}, device_id={entity.device_id}"
            )
