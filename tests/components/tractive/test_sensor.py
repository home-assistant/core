"""Test the Tractive sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

        mock_tractive_client.send_hardware_event(mock_config_entry)
        mock_tractive_client.send_health_overview_event(mock_config_entry)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_device_assignment(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that hardware sensors are on the tracker device and health sensors on the pet device."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    tracker_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_id_123")}
    )
    assert tracker_device is not None

    pet_device = device_registry.async_get_device(identifiers={(DOMAIN, "pet_id_123")})
    assert pet_device is not None

    for entity_id in (
        "sensor.tracker_device_id_123_battery",
        "sensor.tracker_device_id_123_status",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == tracker_device.id

    for entity_id in (
        "sensor.test_pet_activity_time",
        "sensor.test_pet_rest_time",
        "sensor.test_pet_daily_goal",
        "sensor.test_pet_day_sleep",
        "sensor.test_pet_night_sleep",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == pet_device.id
