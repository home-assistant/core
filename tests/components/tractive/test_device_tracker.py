"""Test the Tractive device tracker platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_device_tracker(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the device_tracker."""
    with patch(
        "homeassistant.components.tractive.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await init_integration(hass, mock_config_entry)

        mock_tractive_client.send_position_event(mock_config_entry)
        mock_tractive_client.send_hardware_event(mock_config_entry)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_source_type_phone(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the device tracker with source type phone."""
    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_position_event(
        mock_config_entry,
        {
            "tracker_id": "device_id_123",
            "position": {
                "latlong": [22.333, 44.555],
                "accuracy": 99,
                "sensor_used": "PHONE",
            },
        },
    )
    mock_tractive_client.send_hardware_event(mock_config_entry)
    await hass.async_block_till_done()

    assert (
        hass.states.get("device_tracker.tracker_device_id_123").attributes[
            "source_type"
        ]
        is SourceType.BLUETOOTH
    )


async def test_source_type_gps(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the source type is GPS when the location sensor is KNOWN WIFI."""
    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_position_event(
        mock_config_entry,
        {
            "tracker_id": "device_id_123",
            "position": {
                "latlong": [22.333, 44.555],
                "accuracy": 99,
                "sensor_used": "KNOWN_WIFI",
            },
        },
    )
    mock_tractive_client.send_hardware_event(mock_config_entry)
    await hass.async_block_till_done()

    assert (
        hass.states.get("device_tracker.tracker_device_id_123").attributes[
            "source_type"
        ]
        is SourceType.GPS
    )


async def test_device_tracker_device_assignment(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device tracker entity is assigned to the tracker device."""
    with patch(
        "homeassistant.components.tractive.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await init_integration(hass, mock_config_entry)

    tracker_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_id_123")}
    )
    assert tracker_device is not None

    entry = entity_registry.async_get("device_tracker.tracker_device_id_123")
    assert entry is not None
    assert entry.device_id == tracker_device.id
