"""Debug test to see what devices are created."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


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

        _LOGGER.debug("Setup result: %s", result)

        # List all devices
        devices = device_registry.devices
        _LOGGER.debug("All device IDs: %s", list(devices.keys()))

        for device_id, device in devices.items():
            _LOGGER.debug(
                "Device %s: identifiers=%s, name=%s",
                device_id,
                device.identifiers,
                device.name,
            )

        # Check for our specific device
        device = device_registry.async_get_device(  # type: ignore[assignment]
            identifiers={(DOMAIN, mock_config_entry.entry_id)}
        )
        _LOGGER.debug("Device with config entry ID: %s", device)

        device = device_registry.async_get_device(  # type: ignore[assignment]
            identifiers={(DOMAIN, "ABCD1234567890")}
        )
        _LOGGER.debug("Device with serial: %s", device)

        # Check entities
        entity_registry = er.async_get(hass)
        entities = entity_registry.entities
        _LOGGER.debug("All entity IDs: %s", list(entities.keys()))

        for entity_id, entity in entities.items():
            _LOGGER.debug(
                "Entity %s: platform=%s, device_id=%s",
                entity_id,
                entity.platform,
                entity.device_id,
            )
