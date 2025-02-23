"""Tests for the Amazon Devices integration."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.amazon_devices.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert device_entry is not None
    assert device_entry == snapshot
