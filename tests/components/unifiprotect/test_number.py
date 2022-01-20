"""Test the UniFi Protect number platform."""
# pylint: disable=protected-access
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera, Light

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.number import (
    CAMERA_NUMBERS,
    LIGHT_NUMBERS,
    ProtectNumberEntityDescription,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    ids_from_device_description,
)


@pytest.fixture(name="light")
async def light_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Fixture for a single light for testing the number platform."""

    # disable pydantic validation so mocking can happen
    Light.__config__.validate_assignment = False

    light_obj = mock_light.copy(deep=True)
    light_obj._api = mock_entry.api
    light_obj.name = "Test Light"
    light_obj.light_device_settings.pir_sensitivity = 45
    light_obj.light_device_settings.pir_duration = timedelta(seconds=45)

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.lights = {
        light_obj.id: light_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    yield light_obj

    Light.__config__.validate_assignment = True


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the number platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.can_optical_zoom = True
    camera_obj.feature_flags.has_mic = True
    # has_wdr is an the inverse of has HDR
    camera_obj.feature_flags.has_hdr = False
    camera_obj.isp_settings.wdr = 0
    camera_obj.mic_volume = 0
    camera_obj.isp_settings.zoom_position = 0

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.NUMBER, 3, 3)

    yield camera_obj

    Camera.__config__.validate_assignment = True


async def test_number_setup_light(
    hass: HomeAssistant,
    light: Light,
):
    """Test number entity setup for light devices."""

    entity_registry = er.async_get(hass)

    for description in LIGHT_NUMBERS:
        unique_id, entity_id = ids_from_device_description(
            Platform.NUMBER, light, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "45"
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_number_setup_camera_all(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test number entity setup for camera devices (all features)."""

    entity_registry = er.async_get(hass)

    for description in CAMERA_NUMBERS:
        unique_id, entity_id = ids_from_device_description(
            Platform.NUMBER, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "0"
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_number_setup_camera_none(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Test number entity setup for camera devices (no features)."""

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.can_optical_zoom = False
    camera_obj.feature_flags.has_mic = False
    # has_wdr is an the inverse of has HDR
    camera_obj.feature_flags.has_hdr = True

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


async def test_number_setup_camera_missing_attr(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Test number entity setup for camera devices (no features, bad attrs)."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags = None

    Camera.__config__.validate_assignment = True

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


async def test_number_light_sensitivity(hass: HomeAssistant, light: Light):
    """Test sensitivity number entity for lights."""

    description = LIGHT_NUMBERS[0]
    assert description.ufp_set_method is not None

    light.__fields__["set_sensitivity"] = Mock()
    light.set_sensitivity = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.NUMBER, light, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 15.0}, blocking=True
    )

    light.set_sensitivity.assert_called_once_with(15.0)


async def test_number_light_duration(hass: HomeAssistant, light: Light):
    """Test auto-shutoff duration number entity for lights."""

    description = LIGHT_NUMBERS[1]

    light.__fields__["set_duration"] = Mock()
    light.set_duration = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.NUMBER, light, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 15.0}, blocking=True
    )

    light.set_duration.assert_called_once_with(timedelta(seconds=15.0))


@pytest.mark.parametrize("description", CAMERA_NUMBERS)
async def test_number_camera_simple(
    hass: HomeAssistant, camera: Camera, description: ProtectNumberEntityDescription
):
    """Tests all simple numbers for cameras."""

    assert description.ufp_set_method is not None

    camera.__fields__[description.ufp_set_method] = Mock()
    setattr(camera, description.ufp_set_method, AsyncMock())
    set_method = getattr(camera, description.ufp_set_method)

    _, entity_id = ids_from_device_description(Platform.NUMBER, camera, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 1.0}, blocking=True
    )

    set_method.assert_called_once_with(1.0)
