"""Test the Zinvolt initialization."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Zinvolt device."""
    await setup_integration(hass, mock_config_entry)
    devices = device_registry.devices
    for device in devices.values():
        assert device == snapshot(name=list(device.identifiers)[0][1])
