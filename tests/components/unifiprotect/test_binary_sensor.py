"""Test the UniFi Protect binary_sensor platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from uiprotect.data import (
    Camera,
    Event,
    EventType,
    Light,
    ModelType,
    MountType,
    Sensor,
    SmartDetectObjectType,
)
from uiprotect.data.nvr import EventMetadata

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.unifiprotect.binary_sensor import (
    CAMERA_SENSORS,
    EVENT_SENSORS,
    LIGHT_SENSORS,
    MOUNTABLE_SENSE_SENSORS,
    SENSE_SENSORS,
)
from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_SCORE,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Event as HAEvent, EventStateChangedData, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    remove_entities,
)

from tests.common import async_capture_events

LIGHT_SENSOR_WRITE = LIGHT_SENSORS[:2]
SENSE_SENSORS_WRITE = SENSE_SENSORS[:3]


async def test_binary_sensor_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 9, 6)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 9, 6)


async def test_binary_sensor_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 2, 2)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 2, 2)


async def test_binary_sensor_sensor_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 5, 5)
    await remove_entities(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 0, 0)
    await adopt_devices(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 5, 5)


async def test_binary_sensor_setup_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test binary_sensor entity setup for light devices."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 8, 8)

    for description in LIGHT_SENSOR_WRITE:
        unique_id, entity_id = ids_from_device_description(
            Platform.BINARY_SENSOR, light, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_setup_camera_all(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test binary_sensor entity setup for camera devices (all features)."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 9, 6)

    description = EVENT_SENSORS[0]
    unique_id, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Is Dark
    description = CAMERA_SENSORS[0]
    unique_id, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Motion
    description = EVENT_SENSORS[1]
    unique_id, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_setup_camera_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test binary_sensor entity setup for camera devices (no features)."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 2, 2)

    description = CAMERA_SENSORS[0]

    unique_id, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, camera, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_setup_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Test binary_sensor entity setup for sensor devices."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    expected = [
        STATE_UNAVAILABLE,
        STATE_OFF,
        STATE_OFF,
        STATE_OFF,
    ]
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        unique_id, entity_id = ids_from_device_description(
            Platform.BINARY_SENSOR, sensor_all, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_setup_sensor_leak(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor: Sensor,
) -> None:
    """Test binary_sensor entity setup for sensor with most leak mounting type."""

    sensor.mount_type = MountType.LEAK
    await init_entry(hass, ufp, [sensor])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    expected = [
        STATE_OFF,
        STATE_OFF,
        STATE_UNAVAILABLE,
        STATE_OFF,
    ]
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        unique_id, entity_id = ids_from_device_description(
            Platform.BINARY_SENSOR, sensor, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_update_motion(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test binary_sensor motion entity."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 15, 12)

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, EVENT_SENSORS[1]
    )

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_motion_detected = True
    new_camera.last_motion_event_id = event.id

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 100


async def test_binary_sensor_update_light_motion(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, fixed_now: datetime
) -> None:
    """Test binary_sensor motion entity."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 8, 8)

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, light, LIGHT_SENSOR_WRITE[1]
    )

    event_metadata = EventMetadata(light_id=light.id)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.MOTION_LIGHT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_light = light.copy()
    new_light.is_pir_motion_detected = True
    new_light.last_motion_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    ufp.api.bootstrap.lights = {new_light.id: new_light}
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


async def test_binary_sensor_update_mount_type_window(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Test binary_sensor motion entity."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, sensor_all, MOUNTABLE_SENSE_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR.value

    new_sensor = sensor_all.copy()
    new_sensor.mount_type = MountType.WINDOW

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_sensor

    ufp.api.bootstrap.sensors = {new_sensor.id: new_sensor}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.WINDOW.value


async def test_binary_sensor_update_mount_type_garage(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Test binary_sensor motion entity."""

    await init_entry(hass, ufp, [sensor_all], debug=True)
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, sensor_all, MOUNTABLE_SENSE_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR.value

    new_sensor = sensor_all.copy()
    new_sensor.mount_type = MountType.GARAGE

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_sensor

    ufp.api.bootstrap.sensors = {new_sensor.id: new_sensor}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.GARAGE_DOOR.value
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_package_detected(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test binary_sensor package detection entity."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 15, 15)

    doorbell.smart_detect_settings.object_types.append(SmartDetectObjectType.PACKAGE)

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, EVENT_SENSORS[6]
    )

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[SmartDetectObjectType.PACKAGE],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.PACKAGE] = event.id

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 100

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=50,
        smart_detect_types=[SmartDetectObjectType.PACKAGE],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.PACKAGE] = event.id

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    # Event is already seen and has end, should now be off
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    # Now send an event that has an end right away
    event = Event(
        model=ModelType.EVENT,
        id="new_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=80,
        smart_detect_types=[SmartDetectObjectType.PACKAGE],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.PACKAGE] = event.id

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    state_changes: list[HAEvent[EventStateChangedData]] = async_capture_events(
        hass, EVENT_STATE_CHANGED
    )
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    assert len(state_changes) == 2

    on_event = state_changes[0]
    state = on_event.data["new_state"]
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 80

    off_event = state_changes[1]
    state = off_event.data["new_state"]
    assert state
    assert state.state == STATE_OFF
    assert ATTR_EVENT_SCORE not in state.attributes

    # replay and ensure ignored
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_person_detected(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test binary_sensor person detected detection entity."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 15, 15)

    doorbell.smart_detect_settings.object_types.append(SmartDetectObjectType.PERSON)

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, EVENT_SENSORS[3]
    )

    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=50,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_smart_detected = True

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=65,
        smart_detect_types=[SmartDetectObjectType.PERSON],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.PERSON] = event.id

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    entity_events = [event for event in events if event.data["entity_id"] == entity_id]
    assert len(entity_events) == 3
    assert entity_events[0].data["new_state"].state == STATE_OFF
    assert entity_events[1].data["new_state"].state == STATE_ON
    assert entity_events[2].data["new_state"].state == STATE_OFF

    # Event is already seen and has end, should now be off
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    # Now send an event that has an end right away
    event = Event(
        model=ModelType.EVENT,
        id="new_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=80,
        smart_detect_types=[SmartDetectObjectType.PERSON],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_ids[SmartDetectObjectType.PERSON] = event.id

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    state_changes: list[HAEvent[EventStateChangedData]] = async_capture_events(
        hass, EVENT_STATE_CHANGED
    )
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    assert len(state_changes) == 2

    on_event = state_changes[0]
    state = on_event.data["new_state"]
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 80

    off_event = state_changes[1]
    state = off_event.data["new_state"]
    assert state
    assert state.state == STATE_OFF
    assert ATTR_EVENT_SCORE not in state.attributes

    # replay and ensure ignored
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()
    assert len(state_changes) == 2
