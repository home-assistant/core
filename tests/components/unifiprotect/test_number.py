"""Test the UniFi Protect number platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera, Doorlock, IRLEDMode, Light

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.number import (
    CAMERA_NUMBERS,
    DOORLOCK_NUMBERS,
    LIGHT_NUMBERS,
    ProtectNumberEntityDescription,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    remove_entities,
)


async def test_number_sensor_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    await init_entry(hass, ufp, [camera, unadopted_camera])
    assert_entity_counts(hass, Platform.NUMBER, 4, 4)
    await remove_entities(hass, ufp, [camera, unadopted_camera])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)
    await adopt_devices(hass, ufp, [camera, unadopted_camera])
    assert_entity_counts(hass, Platform.NUMBER, 4, 4)


async def test_number_sensor_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)


async def test_number_lock_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorlock: Doorlock
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.NUMBER, 1, 1)
    await remove_entities(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)
    await adopt_devices(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.NUMBER, 1, 1)


async def test_number_setup_light(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test number entity setup for light devices."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

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
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Test number entity setup for camera devices (all features)."""

    camera.feature_flags.has_chime = True
    camera.chime_duration = timedelta(seconds=1)
    camera.feature_flags.has_led_ir = True
    camera.isp_settings.icr_custom_value = 1
    camera.isp_settings.ir_led_mode = IRLEDMode.CUSTOM
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 5, 5)

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
        assert state.state == "1"
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_number_setup_camera_none(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Test number entity setup for camera devices (no features)."""

    camera.feature_flags.can_optical_zoom = False
    camera.feature_flags.has_mic = False
    # has_wdr is an the inverse of has HDR
    camera.feature_flags.has_hdr = True
    camera.feature_flags.has_led_ir = False

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


async def test_number_setup_camera_missing_attr(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Test number entity setup for camera devices (no features, bad attrs)."""

    camera.feature_flags = None

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


async def test_number_light_sensitivity(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test sensitivity number entity for lights."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    description = LIGHT_NUMBERS[0]
    assert description.ufp_set_method is not None

    light.__fields__["set_sensitivity"] = Mock(final=False)
    light.set_sensitivity = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.NUMBER, light, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 15.0}, blocking=True
    )

    light.set_sensitivity.assert_called_once_with(15.0)


async def test_number_light_duration(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test auto-shutoff duration number entity for lights."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    description = LIGHT_NUMBERS[1]

    light.__fields__["set_duration"] = Mock(final=False)
    light.set_duration = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.NUMBER, light, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 15.0}, blocking=True
    )

    light.set_duration.assert_called_once_with(timedelta(seconds=15.0))


@pytest.mark.parametrize("description", CAMERA_NUMBERS)
async def test_number_camera_simple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    description: ProtectNumberEntityDescription,
) -> None:
    """Tests all simple numbers for cameras."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 4, 4)

    assert description.ufp_set_method is not None

    camera.__fields__[description.ufp_set_method] = Mock(final=False)
    setattr(camera, description.ufp_set_method, AsyncMock())

    _, entity_id = ids_from_device_description(Platform.NUMBER, camera, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 1.0}, blocking=True
    )


async def test_number_lock_auto_close(
    hass: HomeAssistant, ufp: MockUFPFixture, doorlock: Doorlock
) -> None:
    """Test auto-lock timeout for locks."""

    await init_entry(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.NUMBER, 1, 1)

    description = DOORLOCK_NUMBERS[0]

    doorlock.__fields__["set_auto_close_time"] = Mock(final=False)
    doorlock.set_auto_close_time = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.NUMBER, doorlock, description)

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 15.0}, blocking=True
    )

    doorlock.set_auto_close_time.assert_called_once_with(timedelta(seconds=15.0))
