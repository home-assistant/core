"""Test the Tractive device tracker platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
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

        mock_tractive_client.set_tracker_status(
            latitude=22.333, longitude=44.555, accuracy=99, sensor_used="GPS"
        )
        mock_tractive_client.set_tracker_status(
            battery_level=88,
            tracker_state="operational",
            power_saving=True,
            battery_charging=True,
        )
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_source_type_phone(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the device tracker with source type phone."""
    await init_integration(hass, mock_config_entry)

    mock_tractive_client.set_tracker_status(
        latitude=22.333, longitude=44.555, accuracy=99, sensor_used="PHONE"
    )
    mock_tractive_client.set_tracker_status(
        battery_level=88,
        tracker_state="operational",
        power_saving=True,
        battery_charging=True,
    )
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

    mock_tractive_client.set_tracker_status(
        latitude=22.333, longitude=44.555, accuracy=99, sensor_used="KNOWN_WIFI"
    )
    mock_tractive_client.set_tracker_status(
        battery_level=88,
        tracker_state="operational",
        power_saving=True,
        battery_charging=True,
    )
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

    tracker_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "device_id_123"), mock_config_entry.entry_id
    )
    assert tracker_device is not None

    entry = entity_registry.async_get("device_tracker.tracker_device_id_123")
    assert entry is not None
    assert entry.device_id == tracker_device.id


async def test_device_tracker_without_position(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a tracker without a position, like a switched off one, is set up."""
    tracker_status = mock_tractive_client.status.trackers["device_id_123"]
    tracker_status.latitude = None
    tracker_status.longitude = None
    tracker_status.accuracy = None
    tracker_status.sensor_used = None
    with patch(
        "homeassistant.components.tractive.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await init_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.tracker_device_id_123")
    assert state
    assert state.state == STATE_UNKNOWN

    mock_tractive_client.set_tracker_status(
        latitude=22.333, longitude=44.555, accuracy=99, sensor_used="GPS"
    )
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.tracker_device_id_123")
    assert state.state != STATE_UNKNOWN
