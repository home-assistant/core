"""Test the UniFi Protect binary_sensor platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from pyunifiprotect.data import Camera, Event, EventType, Light, MountType, Sensor
from pyunifiprotect.data.nvr import EventMetadata

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.unifiprotect.binary_sensor import (
    CAMERA_SENSORS,
    LIGHT_SENSORS,
    MOTION_SENSORS,
    SENSE_SENSORS,
)
from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_SCORE,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_LAST_TRIP_TIME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    ids_from_device_description,
)


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_camera: Camera,
    now: datetime,
):
    """Fixture for a single camera for testing the binary_sensor platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_chime = True
    camera_obj.last_ring = now - timedelta(hours=1)
    camera_obj.is_dark = False
    camera_obj.is_motion_detected = False

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 3, 3)

    yield camera_obj

    Camera.__config__.validate_assignment = True


@pytest.fixture(name="light")
async def light_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light, now: datetime
):
    """Fixture for a single light for testing the binary_sensor platform."""

    # disable pydantic validation so mocking can happen
    Light.__config__.validate_assignment = False

    light_obj = mock_light.copy(deep=True)
    light_obj._api = mock_entry.api
    light_obj.name = "Test Light"
    light_obj.is_dark = False
    light_obj.is_pir_motion_detected = False
    light_obj.last_motion = now - timedelta(hours=1)

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.lights = {
        light_obj.id: light_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 2, 2)

    yield light_obj

    Light.__config__.validate_assignment = True


@pytest.fixture(name="camera_none")
async def camera_none_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the binary_sensor platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_chime = False
    camera_obj.is_dark = False
    camera_obj.is_motion_detected = False

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 2, 2)

    yield camera_obj

    Camera.__config__.validate_assignment = True


@pytest.fixture(name="sensor")
async def sensor_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_sensor: Sensor,
    now: datetime,
):
    """Fixture for a single sensor for testing the binary_sensor platform."""

    # disable pydantic validation so mocking can happen
    Sensor.__config__.validate_assignment = False

    sensor_obj = mock_sensor.copy(deep=True)
    sensor_obj._api = mock_entry.api
    sensor_obj.name = "Test Sensor"
    sensor_obj.mount_type = MountType.DOOR
    sensor_obj.is_opened = False
    sensor_obj.battery_status.is_low = False
    sensor_obj.is_motion_detected = False
    sensor_obj.alarm_settings.is_enabled = True
    sensor_obj.motion_detected_at = now - timedelta(hours=1)
    sensor_obj.open_status_changed_at = now - timedelta(hours=1)
    sensor_obj.alarm_triggered_at = now - timedelta(hours=1)
    sensor_obj.tampering_detected_at = now - timedelta(hours=1)

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.sensors = {
        sensor_obj.id: sensor_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 4, 4)

    yield sensor_obj

    Sensor.__config__.validate_assignment = True


@pytest.fixture(name="sensor_none")
async def sensor_none_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_sensor: Sensor,
    now: datetime,
):
    """Fixture for a single sensor for testing the binary_sensor platform."""

    # disable pydantic validation so mocking can happen
    Sensor.__config__.validate_assignment = False

    sensor_obj = mock_sensor.copy(deep=True)
    sensor_obj._api = mock_entry.api
    sensor_obj.name = "Test Sensor"
    sensor_obj.mount_type = MountType.LEAK
    sensor_obj.battery_status.is_low = False
    sensor_obj.alarm_settings.is_enabled = False
    sensor_obj.tampering_detected_at = now - timedelta(hours=1)

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.sensors = {
        sensor_obj.id: sensor_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 4, 4)

    yield sensor_obj

    Sensor.__config__.validate_assignment = True


async def test_binary_sensor_setup_light(
    hass: HomeAssistant, light: Light, now: datetime
):
    """Test binary_sensor entity setup for light devices."""

    entity_registry = er.async_get(hass)

    for index, description in enumerate(LIGHT_SENSORS):
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

        if index == 1:
            assert state.attributes[ATTR_LAST_TRIP_TIME] == now - timedelta(hours=1)


async def test_binary_sensor_setup_camera_all(
    hass: HomeAssistant, camera: Camera, now: datetime
):
    """Test binary_sensor entity setup for camera devices (all features)."""

    entity_registry = er.async_get(hass)

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

    assert state.attributes[ATTR_LAST_TRIP_TIME] == now - timedelta(hours=1)

    # Is Dark
    description = CAMERA_SENSORS[1]
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

    # Motion
    description = MOTION_SENSORS[0]
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
    assert state.attributes[ATTR_EVENT_SCORE] == 0


async def test_binary_sensor_setup_camera_none(
    hass: HomeAssistant,
    camera_none: Camera,
):
    """Test binary_sensor entity setup for camera devices (no features)."""

    entity_registry = er.async_get(hass)
    description = CAMERA_SENSORS[1]

    unique_id, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, camera_none, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_setup_sensor(
    hass: HomeAssistant, sensor: Sensor, now: datetime
):
    """Test binary_sensor entity setup for sensor devices."""

    entity_registry = er.async_get(hass)

    expected_trip_time = now - timedelta(hours=1)
    for index, description in enumerate(SENSE_SENSORS):
        unique_id, entity_id = ids_from_device_description(
            Platform.BINARY_SENSOR, sensor, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

        if index != 1:
            assert state.attributes[ATTR_LAST_TRIP_TIME] == expected_trip_time


async def test_binary_sensor_setup_sensor_none(
    hass: HomeAssistant, sensor_none: Sensor
):
    """Test binary_sensor entity setup for sensor with most sensors disabled."""

    entity_registry = er.async_get(hass)

    expected = [
        STATE_UNAVAILABLE,
        STATE_OFF,
        STATE_UNAVAILABLE,
        STATE_OFF,
    ]
    for index, description in enumerate(SENSE_SENSORS):
        unique_id, entity_id = ids_from_device_description(
            Platform.BINARY_SENSOR, sensor_none, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        print(entity_id)
        assert state.state == expected[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_binary_sensor_update_motion(
    hass: HomeAssistant, mock_entry: MockEntityFixture, camera: Camera, now: datetime
):
    """Test binary_sensor motion entity."""

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, camera, MOTION_SENSORS[0]
    )

    event = Event(
        id="test_event_id",
        type=EventType.MOTION,
        start=now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=camera.id,
    )

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera.copy()
    new_camera.is_motion_detected = True
    new_camera.last_motion_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    new_bootstrap.events = {event.id: event}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 100


async def test_binary_sensor_update_light_motion(
    hass: HomeAssistant, mock_entry: MockEntityFixture, light: Light, now: datetime
):
    """Test binary_sensor motion entity."""

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, light, LIGHT_SENSORS[1]
    )

    event_metadata = EventMetadata(light_id=light.id)
    event = Event(
        id="test_event_id",
        type=EventType.MOTION_LIGHT,
        start=now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=mock_entry.api,
    )

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_light = light.copy()
    new_light.is_pir_motion_detected = True
    new_light.last_motion_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    new_bootstrap.lights = {new_light.id: new_light}
    new_bootstrap.events = {event.id: event}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


async def test_binary_sensor_update_mount_type_window(
    hass: HomeAssistant, mock_entry: MockEntityFixture, sensor: Sensor
):
    """Test binary_sensor motion entity."""

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, sensor, SENSE_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR.value

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_sensor = sensor.copy()
    new_sensor.mount_type = MountType.WINDOW

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_sensor

    new_bootstrap.sensors = {new_sensor.id: new_sensor}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.WINDOW.value


async def test_binary_sensor_update_mount_type_garage(
    hass: HomeAssistant, mock_entry: MockEntityFixture, sensor: Sensor
):
    """Test binary_sensor motion entity."""

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, sensor, SENSE_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR.value

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_sensor = sensor.copy()
    new_sensor.mount_type = MountType.GARAGE

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_sensor

    new_bootstrap.sensors = {new_sensor.id: new_sensor}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.GARAGE_DOOR.value
    )
