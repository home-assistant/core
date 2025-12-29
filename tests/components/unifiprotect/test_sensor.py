"""Test the UniFi Protect sensor platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from uiprotect.data import NVR, Camera, Event, EventType, ModelType, Sensor
from uiprotect.data.nvr import EventMetadata

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.sensor import (
    ALL_DEVICES_SENSORS,
    CAMERA_DISABLED_SENSORS,
    CAMERA_SENSORS,
    MOTION_TRIP_SENSORS,
    NVR_DISABLED_SENSORS,
    NVR_SENSORS,
    SENSE_SENSORS,
    ProtectSensorEntityDescription,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    ids_from_device_description,
    init_entry,
    remove_entities,
    reset_objects,
    time_changed,
)


def get_sensor_by_key(sensors: tuple, key: str) -> ProtectSensorEntityDescription:
    """Get sensor description by key."""
    for sensor in sensors:
        if sensor.key == key:
            return sensor
    raise ValueError(f"Sensor with key '{key}' not found")


# Constants for test slicing (subsets of sensor tuples)
CAMERA_SENSORS_WRITE = CAMERA_SENSORS[:5]
SENSE_SENSORS_WRITE = SENSE_SENSORS[:8]


async def test_sensor_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SENSOR, 24, 12)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SENSOR, 12, 9)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SENSOR, 24, 12)


async def test_sensor_sensor_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)
    await remove_entities(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 12, 9)
    await adopt_devices(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)


async def test_sensor_setup_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Test sensor entity setup for sensor devices."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    expected_values = (
        "10",
        "10.0",
        "10.0",
        "10.0",
        "none",
    )
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        if not description.entity_registry_enabled_default:
            continue
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, sensor_all, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # BLE signal
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(ALL_DEVICES_SENSORS, "ble_signal"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "-50"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_sensor_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor: Sensor,
) -> None:
    """Test sensor entity setup for sensor devices with no sensors enabled."""

    await init_entry(hass, ufp, [sensor])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    expected_values = (
        "10",
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
    )
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        if not description.entity_registry_enabled_default:
            continue
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, sensor, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_nvr(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    fixed_now: datetime,
) -> None:
    """Test sensor entity setup for NVR device."""

    reset_objects(ufp.api.bootstrap)
    nvr: NVR = ufp.api.bootstrap.nvr
    nvr.up_since = fixed_now
    nvr.system_info.cpu.average_load = 50.0
    nvr.system_info.cpu.temperature = 50.0
    nvr.storage_stats.utilization = 50.0
    nvr.system_info.memory.available = 50.0
    nvr.system_info.memory.total = 100.0
    nvr.storage_stats.storage_distribution.timelapse_recordings.percentage = 50.0
    nvr.storage_stats.storage_distribution.continuous_recordings.percentage = 50.0
    nvr.storage_stats.storage_distribution.detections_recordings.percentage = 50.0
    nvr.storage_stats.storage_distribution.hd_usage.percentage = 50.0
    nvr.storage_stats.storage_distribution.uhd_usage.percentage = 50.0
    nvr.storage_stats.storage_distribution.free.percentage = 50.0
    nvr.storage_stats.capacity = 50.0

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SENSOR, 12, 9)

    expected_values = (
        fixed_now.replace(second=0, microsecond=0).isoformat(),
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50",
    )
    for index, description in enumerate(NVR_SENSORS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, nvr, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        if not description.entity_registry_enabled_default:
            await enable_entity(hass, ufp.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    expected_values = ("50.0", "50.0", "50.0")
    for index, description in enumerate(NVR_DISABLED_SENSORS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, nvr, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        await enable_entity(hass, ufp.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_nvr_missing_values(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, ufp: MockUFPFixture
) -> None:
    """Test NVR sensor sensors if no data available."""

    reset_objects(ufp.api.bootstrap)
    nvr: NVR = ufp.api.bootstrap.nvr
    nvr.system_info.memory.available = None
    nvr.system_info.memory.total = None
    nvr.up_since = None
    nvr.storage_stats.capacity = None

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SENSOR, 12, 9)

    # Uptime
    description = get_sensor_by_key(NVR_SENSORS, "uptime")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Recording capacity
    description = get_sensor_by_key(NVR_SENSORS, "record_capacity")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Memory utilization
    description = get_sensor_by_key(NVR_DISABLED_SENSORS, "memory_utilization")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    fixed_now: datetime,
) -> None:
    """Test sensor entity setup for camera devices."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SENSOR, 24, 12)

    expected_values = (
        fixed_now.replace(microsecond=0).isoformat(),
        "0.0001",
        "0.0001",
        "20.0",
    )
    for index, description in enumerate(CAMERA_SENSORS_WRITE):
        if not description.entity_registry_enabled_default:
            continue
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, doorbell, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    expected_values = ("0.0001", "0.0001")
    for index, description in enumerate(CAMERA_DISABLED_SENSORS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, doorbell, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        await enable_entity(hass, ufp.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Wired signal (phy_rate / link speed)
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        doorbell,
        get_sensor_by_key(ALL_DEVICES_SENSORS, "phy_rate"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1000"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Wi-Fi signal
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        doorbell,
        get_sensor_by_key(ALL_DEVICES_SENSORS, "wifi_signal"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "-50"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup_camera_with_last_trip_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    fixed_now: datetime,
) -> None:
    """Test sensor entity setup for camera devices with last trip time."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SENSOR, 24, 24)

    # Last Trip Time
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        doorbell,
        get_sensor_by_key(MOTION_TRIP_SENSORS, "motion_last_trip_time"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.state
        == (fixed_now - timedelta(hours=1)).replace(microsecond=0).isoformat()
    )
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_update_alarm(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor, fixed_now: datetime
) -> None:
    """Test sensor motion entity."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    _, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(SENSE_SENSORS, "alarm_sound"),
    )

    event_metadata = EventMetadata(sensor_id=sensor_all.id, alarm_type="smoke")
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SENSOR_ALARM,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_sensor = sensor_all.model_copy()
    new_sensor.set_alarm_timeout()
    new_sensor.last_alarm_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    ufp.api.bootstrap.sensors = {new_sensor.id: new_sensor}
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "smoke"
    await time_changed(hass, 10)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_update_alarm_with_last_trip_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    fixed_now: datetime,
) -> None:
    """Test sensor motion entity with last trip time."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 22)

    # Last Trip Time
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(SENSE_SENSORS, "door_last_trip_time"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.state
        == (fixed_now - timedelta(hours=1)).replace(microsecond=0).isoformat()
    )
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_precision(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor, fixed_now: datetime
) -> None:
    """Test sensor precision value is respected."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)
    nvr: NVR = ufp.api.bootstrap.nvr

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, get_sensor_by_key(NVR_SENSORS, "resolution_4K")
    )

    assert hass.states.get(entity_id).state == "17.49"
