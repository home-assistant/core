"""Test the Tractive binary sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the binary sensor."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, mock_config_entry)

        mock_tractive_client.send_hardware_event(mock_config_entry)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_device_assignment(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that binary sensor entities are assigned to the tracker device."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, mock_config_entry)

    tracker_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_id_123")}
    )
    assert tracker_device is not None

    for entity_id in (
        "binary_sensor.tracker_device_id_123_charging",
        "binary_sensor.tracker_device_id_123_power_saving",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == tracker_device.id
