"""Tests for the Tuya component."""

from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import patch

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya import DeviceListener
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
DEVICE_MOCKS = sorted(
    str(path.relative_to(FIXTURES_DIR).with_suffix(""))
    for path in FIXTURES_DIR.glob("*.json")
)


class MockDeviceListener(DeviceListener):
    """Mocked DeviceListener for testing."""

    async def async_send_device_update(
        self,
        hass: HomeAssistant,
        device: CustomerDevice,
        updated_status_properties: dict[str, Any] | None = None,
    ) -> None:
        """Mock update device method."""
        property_list: list[str] = []
        if updated_status_properties:
            for key, value in updated_status_properties.items():
                if key not in device.status:
                    raise ValueError(
                        f"Property {key} not found in device status: {device.status}"
                    )
                device.status[key] = value
                property_list.append(key)
        self.update_device(device, property_list)
        await hass.async_block_till_done()


async def initialize_entry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: CustomerDevice | list[CustomerDevice],
) -> None:
    """Initialize the Tuya component with a mock manager and config entry."""
    if not isinstance(mock_devices, list):
        mock_devices = [mock_devices]
    mock_manager.device_map = {device.id: device for device in mock_devices}

    # Setup
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with patch("homeassistant.components.tuya.Manager", return_value=mock_manager):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
