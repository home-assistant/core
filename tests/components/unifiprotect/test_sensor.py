"""Test the UniFi Protect sensor platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from pyunifiprotect.data import NVR, Camera, Event, Sensor
from pyunifiprotect.data.base import WifiConnectionState, WiredConnectionState
from pyunifiprotect.data.nvr import EventMetadata
from pyunifiprotect.data.types import EventType, SmartDetectObjectType

from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_SCORE,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.components.unifiprotect.sensor import (
    ALL_DEVICES_SENSORS,
    CAMERA_DISABLED_SENSORS,
    CAMERA_SENSORS,
    MOTION_SENSORS,
    NVR_DISABLED_SENSORS,
    NVR_SENSORS,
    OBJECT_TYPE_NONE,
    SENSE_SENSORS,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    enable_entity,
    ids_from_device_description,
    time_changed,
)


@pytest.fixture(name="sensor")
async def sensor_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_sensor: Sensor,
    now: datetime,
):
    """Fixture for a single sensor for testing the sensor platform."""

    # disable pydantic validation so mocking can happen
    Sensor.__config__.validate_assignment = False

    sensor_obj = mock_sensor.copy(deep=True)
    sensor_obj._api = mock_entry.api
    sensor_obj.name = "Test Sensor"
    sensor_obj.battery_status.percentage = 10.0
    sensor_obj.light_settings.is_enabled = True
    sensor_obj.humidity_settings.is_enabled = True
    sensor_obj.temperature_settings.is_enabled = True
    sensor_obj.alarm_settings.is_enabled = True
    sensor_obj.stats.light.value = 10.0
    sensor_obj.stats.humidity.value = 10.0
    sensor_obj.stats.temperature.value = 10.0
    sensor_obj.up_since = now
    sensor_obj.bluetooth_connection_state.signal_strength = -50.0

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.sensors = {
        sensor_obj.id: sensor_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    # 2 from all, 4 from sense, 12 NVR
    assert_entity_counts(hass, Platform.SENSOR, 19, 14)

    yield sensor_obj

    Sensor.__config__.validate_assignment = True


@pytest.fixture(name="sensor_none")
async def sensor_none_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_sensor: Sensor,
    now: datetime,
):
    """Fixture for a single sensor for testing the sensor platform."""

    # disable pydantic validation so mocking can happen
    Sensor.__config__.validate_assignment = False

    sensor_obj = mock_sensor.copy(deep=True)
    sensor_obj._api = mock_entry.api
    sensor_obj.name = "Test Sensor"
    sensor_obj.battery_status.percentage = 10.0
    sensor_obj.light_settings.is_enabled = False
    sensor_obj.humidity_settings.is_enabled = False
    sensor_obj.temperature_settings.is_enabled = False
    sensor_obj.alarm_settings.is_enabled = False
    sensor_obj.up_since = now
    sensor_obj.bluetooth_connection_state.signal_strength = -50.0

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.sensors = {
        sensor_obj.id: sensor_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    # 2 from all, 4 from sense, 12 NVR
    assert_entity_counts(hass, Platform.SENSOR, 19, 14)

    yield sensor_obj

    Sensor.__config__.validate_assignment = True


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_camera: Camera,
    now: datetime,
):
    """Fixture for a single camera for testing the sensor platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_smart_detect = True
    camera_obj.is_smart_detected = False
    camera_obj.wired_connection_state = WiredConnectionState(phy_rate=1000)
    camera_obj.wifi_connection_state = WifiConnectionState(
        signal_quality=100, signal_strength=-50
    )
    camera_obj.stats.rx_bytes = 100.0
    camera_obj.stats.tx_bytes = 100.0
    camera_obj.stats.video.recording_start = now
    camera_obj.stats.storage.used = 100.0
    camera_obj.stats.storage.used = 100.0
    camera_obj.stats.storage.rate = 100.0
    camera_obj.voltage = 20.0

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    # 3 from all, 6 from camera, 12 NVR
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    yield camera_obj

    Camera.__config__.validate_assignment = True


async def test_sensor_setup_sensor(
    hass: HomeAssistant, mock_entry: MockEntityFixture, sensor: Sensor
):
    """Test sensor entity setup for sensor devices."""

    entity_registry = er.async_get(hass)

    expected_values = ("10", "10.0", "10.0", "10.0", "none")
    for index, description in enumerate(SENSE_SENSORS):
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

    # BLE signal
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, sensor, ALL_DEVICES_SENSORS[1]
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "-50"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_sensor_none(
    hass: HomeAssistant, mock_entry: MockEntityFixture, sensor_none: Sensor
):
    """Test sensor entity setup for sensor devices with no sensors enabled."""

    entity_registry = er.async_get(hass)

    expected_values = (
        "10",
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
    )
    for index, description in enumerate(SENSE_SENSORS):
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, sensor_none, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_nvr(
    hass: HomeAssistant, mock_entry: MockEntityFixture, now: datetime
):
    """Test sensor entity setup for NVR device."""

    mock_entry.api.bootstrap.reset_objects()
    nvr: NVR = mock_entry.api.bootstrap.nvr
    nvr.up_since = now
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

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    # 2 from all, 4 from sense, 12 NVR
    assert_entity_counts(hass, Platform.SENSOR, 12, 9)

    entity_registry = er.async_get(hass)

    expected_values = (
        now.replace(second=0, microsecond=0).isoformat(),
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
            await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

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

        await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_nvr_missing_values(
    hass: HomeAssistant, mock_entry: MockEntityFixture, now: datetime
):
    """Test NVR sensor sensors if no data available."""

    mock_entry.api.bootstrap.reset_objects()
    nvr: NVR = mock_entry.api.bootstrap.nvr
    nvr.system_info.memory.available = None
    nvr.system_info.memory.total = None
    nvr.up_since = None
    nvr.storage_stats.capacity = None

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    # 2 from all, 4 from sense, 12 NVR
    assert_entity_counts(hass, Platform.SENSOR, 12, 9)

    entity_registry = er.async_get(hass)

    # Uptime
    description = NVR_SENSORS[0]
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

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

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_camera(
    hass: HomeAssistant, mock_entry: MockEntityFixture, camera: Camera, now: datetime
):
    """Test sensor entity setup for camera devices."""

    entity_registry = er.async_get(hass)

    expected_values = (
        now.replace(microsecond=0).isoformat(),
        "100",
        "100.0",
        "20.0",
    )
    for index, description in enumerate(CAMERA_SENSORS):
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    expected_values = ("100", "100")
    for index, description in enumerate(CAMERA_DISABLED_SENSORS):
        unique_id, entity_id = ids_from_device_description(
            Platform.SENSOR, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Wired signal
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, ALL_DEVICES_SENSORS[2]
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1000"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # WiFi signal
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, ALL_DEVICES_SENSORS[3]
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "-50"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Detected Object
    unique_id, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, MOTION_SENSORS[0]
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == OBJECT_TYPE_NONE
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 0


async def test_sensor_update_motion(
    hass: HomeAssistant, mock_entry: MockEntityFixture, camera: Camera, now: datetime
):
    """Test sensor motion entity."""

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, camera, MOTION_SENSORS[0]
    )

    event = Event(
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[SmartDetectObjectType.PERSON],
        smart_detect_event_ids=[],
        camera_id=camera.id,
        api=mock_entry.api,
    )

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera.copy()
    new_camera.is_smart_detected = True
    new_camera.last_smart_detect_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    new_bootstrap.cameras = {new_camera.id: new_camera}
    new_bootstrap.events = {event.id: event}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == SmartDetectObjectType.PERSON.value
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 100


async def test_sensor_update_alarm(
    hass: HomeAssistant, mock_entry: MockEntityFixture, sensor: Sensor, now: datetime
):
    """Test sensor motion entity."""

    _, entity_id = ids_from_device_description(
        Platform.SENSOR, sensor, SENSE_SENSORS[4]
    )

    event_metadata = EventMetadata(sensor_id=sensor.id, alarm_type="smoke")
    event = Event(
        id="test_event_id",
        type=EventType.SENSOR_ALARM,
        start=now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=mock_entry.api,
    )

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_sensor = sensor.copy()
    new_sensor.set_alarm_timeout()
    new_sensor.last_alarm_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    new_bootstrap.sensors = {new_sensor.id: new_sensor}
    new_bootstrap.events = {event.id: event}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "smoke"
    await time_changed(hass, 10)
