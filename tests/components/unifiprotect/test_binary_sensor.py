"""Test the UniFi Protect binary_sensor platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from pyunifiprotect.data import Camera, Light
from pyunifiprotect.data.devices import Sensor

from homeassistant.components.unifiprotect.binary_sensor import (
    CAMERA_SENSORS,
    LIGHT_SENSORS,
    SENSE_SENSORS,
)
from homeassistant.components.unifiprotect.const import (
    DEFAULT_ATTRIBUTION,
    RING_INTERVAL,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LAST_TRIP_TIME,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    ids_from_device_description,
    time_changed,
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

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 1, 1)

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
    sensor_obj.is_opened = False
    sensor_obj.battery_status.is_low = False
    sensor_obj.is_motion_detected = False
    sensor_obj.motion_detected_at = now - timedelta(hours=1)
    sensor_obj.open_status_changed_at = now - timedelta(hours=1)

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.sensors = {
        sensor_obj.id: sensor_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BINARY_SENSOR, 3, 3)

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

    for index, description in enumerate(CAMERA_SENSORS):
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

        if index == 0:
            assert state.attributes[ATTR_LAST_TRIP_TIME] == now - timedelta(hours=1)


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


async def test_binary_sensor_update_doorbell(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: Camera,
):
    """Test select entity update (change doorbell message)."""

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, camera, CAMERA_SENSORS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera.copy()
    new_camera.last_ring = utcnow()

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    # fire event a second time for code coverage (cancel existing)
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    # since time is not really changing, switch the last ring back to allow turn off
    new_camera.last_ring = utcnow() - RING_INTERVAL
    await time_changed(hass, RING_INTERVAL.total_seconds())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
