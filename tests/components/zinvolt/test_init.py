"""Test the Zinvolt initialization."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zinvolt.const import DOMAIN
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
    devices = device_registry._devices
    for device in devices.values():
        assert device == snapshot(name=list(device.identifiers)[0][1])


async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
) -> None:
    """Test that a unit sub-device links to its main battery device via via_device_id."""
    await setup_integration(hass, mock_config_entry)

    battery_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ZVG011025120088"), mock_config_entry.entry_id
    )
    assert battery_device is not None

    unit_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "BAT002"), mock_config_entry.entry_id
    )
    assert unit_device is not None
    assert unit_device.via_device_id == battery_device.id
