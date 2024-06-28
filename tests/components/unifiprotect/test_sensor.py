"""Test the UniFi Protect sensor platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from uiprotect.data import (
    NVR,
    Camera,
    Event,
    EventType,
    ModelType,
    Sensor,
    SmartDetectObjectType,
)
from uiprotect.data.nvr import EventMetadata, LicensePlateMetadata

from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_SCORE,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.components.unifiprotect.sensor import (
    ALL_DEVICES_SENSORS,
    CAMERA_DISABLED_SENSORS,
    CAMERA_SENSORS,
    LICENSE_PLATE_EVENT_SENSORS,
    MOTION_TRIP_SENSORS,
    NVR_DISABLED_SENSORS,
    NVR_SENSORS,
    SENSE_SENSORS,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Event as HAEvent, EventStateChangedData, HomeAssistant
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

from tests.common import async_capture_events

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
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, sensor_all, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # BLE signal
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, sensor_all, ALL_DEVICES_SENSORS[1]
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
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, sensor, description
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
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, nvr, description
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
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, nvr, description
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
    description = NVR_SENSORS[0]
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Memory
    description = NVR_SENSORS[8]
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Memory
    description = NVR_DISABLED_SENSORS[2]
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, nvr, description
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
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, doorbell, description
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
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, doorbell, description
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

    # Wired signal
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, doorbell, ALL_DEVICES_SENSORS[2]
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

    # WiFi signal
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, doorbell, ALL_DEVICES_SENSORS[3]
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
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, doorbell, MOTION_TRIP_SENSORS[0]
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

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[4]
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

    new_sensor = sensor_all.copy()
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
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[-3]
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


async def test_camera_update_license_plate(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera, fixed_now: datetime
) -> None:
    """Test license plate sensor."""

    camera.feature_flags.smart_detect_types.append(SmartDetectObjectType.LICENSE_PLATE)
    camera.feature_flags.has_smart_detect = True
    camera.smart_detect_settings.object_types.append(
        SmartDetectObjectType.LICENSE_PLATE
    )

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SENSOR, 23, 13)

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, LICENSE_PLATE_EVENT_SENSORS[0]
    )

    event_metadata = EventMetadata(
        license_plate=LicensePlateMetadata(name="ABCD1234", confidence_level=95)
    )
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[SmartDetectObjectType.LICENSE_PLATE],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_camera = camera.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.LICENSE_PLATE] = (
        event.id
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    state_changes: list[HAEvent[EventStateChangedData]] = async_capture_events(
        hass, EVENT_STATE_CHANGED
    )
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "ABCD1234"

    assert len(state_changes) == 1

    # ensure reply is ignored
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 1

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=100,
        smart_detect_types=[SmartDetectObjectType.LICENSE_PLATE],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    ufp.api.bootstrap.events = {event.id: event}
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.LICENSE_PLATE] = (
        event.id
    )
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 2
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"

    # Now send a new event with end already set
    event = Event(
        model=ModelType.EVENT,
        id="new_event",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=100,
        smart_detect_types=[SmartDetectObjectType.LICENSE_PLATE],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    ufp.api.bootstrap.events = {event.id: event}
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.LICENSE_PLATE] = (
        event.id
    )
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 4
    assert state_changes[2].data["new_state"].state == "ABCD1234"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"


async def test_camera_update_license_plate_changes_number_during_detect(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera, fixed_now: datetime
) -> None:
    """Test license plate sensor that changes number during detect."""

    camera.feature_flags.smart_detect_types.append(SmartDetectObjectType.LICENSE_PLATE)
    camera.feature_flags.has_smart_detect = True
    camera.smart_detect_settings.object_types.append(
        SmartDetectObjectType.LICENSE_PLATE
    )

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SENSOR, 23, 13)

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, LICENSE_PLATE_EVENT_SENSORS[0]
    )

    event_metadata = EventMetadata(
        license_plate=LicensePlateMetadata(name="ABCD1234", confidence_level=95)
    )
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[SmartDetectObjectType.LICENSE_PLATE],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_camera = camera.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.LICENSE_PLATE] = (
        event.id
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    state_changes: list[HAEvent[EventStateChangedData]] = async_capture_events(
        hass, EVENT_STATE_CHANGED
    )
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "ABCD1234"

    assert len(state_changes) == 1

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 1

    # Now mutate the original event so it ends
    # Also change the metadata to a different license plate
    # since the model may not get the plate correct on
    # the first update.
    event.score = 99
    event.end = fixed_now + timedelta(seconds=1)
    event_metadata.license_plate.name = "DCBA4321"
    ufp.api.bootstrap.events = {event.id: event}

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 3
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"

    assert state_changes[0].data["new_state"].state == "ABCD1234"
    assert state_changes[1].data["new_state"].state == "DCBA4321"
    assert state_changes[2].data["new_state"].state == "none"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"


async def test_camera_update_license_plate_multiple_updates(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera, fixed_now: datetime
) -> None:
    """Test license plate sensor that updates multiple times."""

    camera.feature_flags.smart_detect_types.append(SmartDetectObjectType.LICENSE_PLATE)
    camera.feature_flags.has_smart_detect = True
    camera.smart_detect_settings.object_types.append(
        SmartDetectObjectType.LICENSE_PLATE
    )

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SENSOR, 23, 13)

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, LICENSE_PLATE_EVENT_SENSORS[0]
    )

    event_metadata = EventMetadata(
        license_plate=LicensePlateMetadata(name="ABCD1234", confidence_level=95)
    )
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[SmartDetectObjectType.LICENSE_PLATE],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_camera = camera.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.LICENSE_PLATE] = (
        event.id
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    state_changes: list[HAEvent[EventStateChangedData]] = async_capture_events(
        hass, EVENT_STATE_CHANGED
    )
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "ABCD1234"
    assert state.attributes[ATTR_EVENT_SCORE] == 100

    assert len(state_changes) == 1

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 1

    # Now mutate the original event so the score changes
    event.score = 99
    event_metadata.license_plate.name = "DCBA4321"
    ufp.api.bootstrap.events = {event.id: event}

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 2
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "DCBA4321"
    assert state.attributes[ATTR_EVENT_SCORE] == 99

    # Now mutate the original event so the score changes again
    event.score = 40
    ufp.api.bootstrap.events = {event.id: event}

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 3
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "DCBA4321"
    assert state.attributes[ATTR_EVENT_SCORE] == 40

    # Now send the event again
    ufp.api.bootstrap.events = {event.id: event}

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 3
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "DCBA4321"
    assert state.attributes[ATTR_EVENT_SCORE] == 40

    # Now mutate the original event to add an end time
    event.end = fixed_now + timedelta(seconds=1)
    ufp.api.bootstrap.events = {event.id: event}

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 4
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"

    # Now send the event again
    event.end = fixed_now + timedelta(seconds=1)
    ufp.api.bootstrap.events = {event.id: event}

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 4
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"


async def test_camera_update_license_no_dupes(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera, fixed_now: datetime
) -> None:
    """Test license plate sensor does not generate duplicate reads."""

    camera.feature_flags.smart_detect_types.append(SmartDetectObjectType.LICENSE_PLATE)
    camera.feature_flags.has_smart_detect = True
    camera.smart_detect_settings.object_types.append(
        SmartDetectObjectType.LICENSE_PLATE
    )

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SENSOR, 23, 13)

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, LICENSE_PLATE_EVENT_SENSORS[0]
    )

    event_metadata = EventMetadata(
        license_plate=LicensePlateMetadata(name="FPR2238", confidence_level=91)
    )
    event = Event(
        model=ModelType.EVENT,
        id="6675e36400de8c03e40bd5e3",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=83,
        smart_detect_types=[SmartDetectObjectType.LICENSE_PLATE],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_camera = camera.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.LICENSE_PLATE] = (
        event.id
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    state_changes: list[HAEvent[EventStateChangedData]] = async_capture_events(
        hass, EVENT_STATE_CHANGED
    )
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "FPR2238"
    assert state.attributes[ATTR_EVENT_SCORE] == 83

    assert len(state_changes) == 1

    # Now send it again
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 1

    # Again send it again
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 1

    # Now add the end time and change the confidence level
    event.end = fixed_now + timedelta(seconds=1)
    event.metadata.license_plate.confidence_level = 96
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 2

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "none"

    # Now send it 3 more times
    for _ in range(3):
        ufp.api.bootstrap.events = {event.id: event}
        ufp.ws_msg(mock_msg)
        await hass.async_block_till_done()
        assert len(state_changes) == 2

    # Now clear the event
    ufp.api.bootstrap.events = {}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 2


async def test_sensor_precision(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor, fixed_now: datetime
) -> None:
    """Test sensor precision value is respected."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)
    nvr: NVR = ufp.api.bootstrap.nvr

    _, entity_id = ids_from_device_description(Platform.SENSOR, nvr, NVR_SENSORS[6])

    assert hass.states.get(entity_id).state == "17.49"
