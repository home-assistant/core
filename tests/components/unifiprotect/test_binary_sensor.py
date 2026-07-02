"""Test the UniFi Protect binary_sensor platform."""

from collections.abc import Callable
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from uiprotect.data import (
    AiPort,
    Camera,
    Event,
    EventType,
    Light,
    ModelType,
    MountType,
    Sensor,
    SmartDetectAudioType,
)
from uiprotect.data.nvr import EventMetadata
from uiprotect.websocket import WebsocketState

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.unifiprotect.binary_sensor import (
    CAMERA_SENSORS,
    EVENT_SENSORS,
    LIGHT_SENSORS,
    MOUNTABLE_SENSE_SENSORS,
    SENSE_SENSORS,
)
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    make_public_camera,
    make_public_sensor,
    public_device_ws_message,
    remove_entities,
    setup_public_camera,
    setup_public_sensor,
)

from tests.common import async_capture_events

LIGHT_SENSOR_WRITE = LIGHT_SENSORS[:2]
SENSE_SENSORS_WRITE = SENSE_SENSORS[:3]
BATTERY_LOW = next(d for d in SENSE_SENSORS if d.key == "battery_low")
SENSE_MOTION = next(d for d in SENSE_SENSORS if d.key == "motion")


async def test_binary_sensor_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 8, 6)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 8, 6)


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
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.BINARY_SENSOR, light, description
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
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 8, 6)

    description = EVENT_SENSORS[0]
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, description
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
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Motion (migrated to the public path, available via setup_public_camera)
    description = next(d for d in CAMERA_SENSORS if d.key == "motion")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, description
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

    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, camera, description
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

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    expected = [
        STATE_UNAVAILABLE,
        STATE_OFF,
        STATE_OFF,
        STATE_OFF,
    ]
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.BINARY_SENSOR, sensor_all, description
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
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    expected = [
        STATE_OFF,
        STATE_OFF,
        STATE_UNAVAILABLE,
        STATE_OFF,
    ]
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.BINARY_SENSOR, sensor, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_battery_low_public_ws_update(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """battery_low refreshes from a public devices WS update."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, BATTERY_LOW
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    public = make_public_sensor(sensor_all, is_low=True)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_binary_sensor_battery_low_unavailable_without_public_api(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """The migrated battery_low entity is unavailable without a public object."""
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, BATTERY_LOW
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_binary_sensor_sense_motion_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """The sense motion sensor reads is_motion_detected from a public WS update."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, SENSE_MOTION
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    public = make_public_sensor(sensor_all, is_motion_detected=True)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_binary_sensor_sense_motion_disabled_unavailable(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """ufp_public_enabled_fn marks the motion sensor unavailable when disabled."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, SENSE_MOTION
    )
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    public = make_public_sensor(sensor_all, motion_enabled=False)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_binary_sensor_sense_motion_leak_mount_unavailable(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """A leak-mounted sensor reports motion unavailable (mirrors the private gate)."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, SENSE_MOTION
    )

    public = make_public_sensor(sensor_all, mount_type=MountType.LEAK)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_binary_sensor_sense_motion_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """The migrated motion sensor is unavailable without a public object."""
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, SENSE_MOTION
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_binary_sensor_battery_low_unavailable_on_public_ws_disconnect(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """battery_low follows the public websocket health, not the private one."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, BATTERY_LOW
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_binary_sensor_update_motion(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test the migrated motion binary sensor reads sustained state from the public API."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 14, 12)

    motion = next(d for d in CAMERA_SENSORS if d.key == "motion")
    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, motion
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    ufp.devices_ws_subscription(
        public_device_ws_message(make_public_camera(doorbell, is_motion_detected=True))
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON

    # Detection ends -> sustained state clears.
    ufp.devices_ws_subscription(public_device_ws_message(make_public_camera(doorbell)))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_binary_sensor_update_light_motion(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, fixed_now: datetime
) -> None:
    """Test binary_sensor motion entity."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 8, 8)

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, light, LIGHT_SENSOR_WRITE[1]
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

    new_light = light.model_copy()
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

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, MOUNTABLE_SENSE_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR.value

    new_sensor = sensor_all.model_copy()
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

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 11, 11)

    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, sensor_all, MOUNTABLE_SENSE_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR.value

    new_sensor = sensor_all.model_copy()
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
async def test_binary_sensor_person_detected(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test the migrated person-detection binary sensor over the public API."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 14, 14)

    person = next(d for d in CAMERA_SENSORS if d.key == "smart_obj_person")
    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, person
    )

    assert hass.states.get(entity_id).state == STATE_OFF

    # Person detection starts (camera update pushed on the public devices WS).
    ufp.devices_ws_subscription(
        public_device_ws_message(
            make_public_camera(
                doorbell,
                is_smart_currently_detected=True,
                is_person_currently_detected=True,
            )
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON

    # Detection ends -> sustained state clears.
    ufp.devices_ws_subscription(public_device_ws_message(make_public_camera(doorbell)))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("key", "make_disabled"),
    [
        ("smart_obj_person", lambda c: make_public_camera(c, object_types=[])),
        ("smart_audio_smoke", lambda c: make_public_camera(c, audio_types=[])),
    ],
)
async def test_binary_sensor_detection_disabled_unavailable(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    key: str,
    make_disabled: Callable[[Camera], Mock],
) -> None:
    """A migrated detection binary is unavailable when its type is disabled in Protect."""

    # Ensure the audio-alarm capability so the smoke binary is created.
    doorbell.feature_flags.smart_detect_audio_types = [SmartDetectAudioType.SMOKE]
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell, unadopted_camera])

    description = next(d for d in CAMERA_SENSORS if d.key == key)
    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, description
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    # The detection type is turned off in Protect -> the enabled gate fails.
    ufp.devices_ws_subscription(public_device_ws_message(make_disabled(doorbell)))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_binary_sensor_doorbell_ring(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """The doorbell occupancy binary stays on the private ring event path."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])

    description = next(d for d in EVENT_SENSORS if d.key == "doorbell")
    _, entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, description
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    event = Event(
        model=ModelType.EVENT,
        id="ring-1",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )
    new_camera = doorbell.model_copy()
    new_camera.last_ring_event_id = event.id
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    # A momentary ring blips on, then immediately clears.
    ring_changes = [e for e in state_changes if e.data["entity_id"] == entity_id]
    assert any(c.data["new_state"].state == STATE_ON for c in ring_changes)
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_aiport_no_binary_sensor_entities(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    aiport: AiPort,
) -> None:
    """Test AI Port devices do not create camera-specific binary sensors."""
    await init_entry(hass, ufp, [aiport])

    # AI Port should not create any camera-specific binary sensors
    # (motion, smart detection, etc.)
    # NVR HDD sensors will still be created, but no AI Port-specific entities
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, ufp.entry.entry_id)

    for entity in entities:
        if entity.domain == Platform.BINARY_SENSOR:
            # No entities should contain the AI Port's device id
            assert aiport.id not in entity.unique_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_simultaneous_person_and_vehicle_detection(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Person and vehicle detected at once both report ON.

    Regression for https://github.com/home-assistant/core/issues/152133 (a second
    type added to an ongoing detection): on the public path each type's sustained
    state is derived independently by the library, so adding person to an ongoing
    vehicle detection turns both ON without queueing.
    """

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.BINARY_SENSOR, 14, 14)

    person = next(d for d in CAMERA_SENSORS if d.key == "smart_obj_person")
    vehicle = next(d for d in CAMERA_SENSORS if d.key == "smart_obj_vehicle")
    _, person_entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, person
    )
    _, vehicle_entity_id = await ids_from_device_description(
        hass, Platform.BINARY_SENSOR, doorbell, vehicle
    )

    # Vehicle arrives.
    ufp.devices_ws_subscription(
        public_device_ws_message(
            make_public_camera(
                doorbell,
                is_smart_currently_detected=True,
                is_vehicle_currently_detected=True,
            )
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(vehicle_entity_id).state == STATE_ON
    assert hass.states.get(person_entity_id).state == STATE_OFF

    # Person joins the same scene -> both ON simultaneously.
    ufp.devices_ws_subscription(
        public_device_ws_message(
            make_public_camera(
                doorbell,
                is_smart_currently_detected=True,
                is_vehicle_currently_detected=True,
                is_person_currently_detected=True,
            )
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(vehicle_entity_id).state == STATE_ON
    assert hass.states.get(person_entity_id).state == STATE_ON

    # Scene clears -> both OFF.
    ufp.devices_ws_subscription(public_device_ws_message(make_public_camera(doorbell)))
    await hass.async_block_till_done()

    assert hass.states.get(vehicle_entity_id).state == STATE_OFF
    assert hass.states.get(person_entity_id).state == STATE_OFF
