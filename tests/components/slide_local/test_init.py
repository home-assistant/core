"""Tests for the Slide Local integration."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "1234567890ab")}
    )
    assert device_entry is not None
    assert device_entry == snapshot
