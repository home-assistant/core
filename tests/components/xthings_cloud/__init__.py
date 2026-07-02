"""Tests for the Xthings Cloud integration."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_device_by_id(mock_api_client: AsyncMock, device_id: str) -> dict[str, Any]:
    """Helper for getting the device."""
    for device in mock_api_client.async_get_devices.return_value:
        if device["id"] == device_id:
            return device
    raise ValueError(f"Device with ID {device_id} not found in mock API client.")
