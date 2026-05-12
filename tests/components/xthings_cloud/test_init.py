"""Tests for the Xthings Cloud integration."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.xthings_cloud.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all devices."""
    await setup_integration(hass, mock_config_entry)

    for device in mock_api_client.async_get_devices.return_value:
        device_entry = device_registry.async_get_device({(DOMAIN, device["id"])})

        assert device_entry is not None
        assert device_entry == snapshot(name=device["model"])
