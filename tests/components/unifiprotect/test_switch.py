"""Test the UniFi Protect switch platform."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera, Light, Permission, RecordingMode, VideoMode

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.switch import (
    CAMERA_SWITCHES,
    LIGHT_SWITCHES,
    ProtectSwitchEntityDescription,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, STATE_OFF, Platform
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
)

CAMERA_SWITCHES_BASIC = [
    d
    for d in CAMERA_SWITCHES
    if d.name != "Detections: Face"
    and d.name != "Detections: Package"
    and d.name != "SSH Enabled"
]
CAMERA_SWITCHES_NO_EXTRA = [
    d for d in CAMERA_SWITCHES_BASIC if d.name not in ("High FPS", "Privacy Mode")
]


async def test_switch_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
):
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)
    await remove_entities(hass, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)


async def test_switch_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 2, 1)
    await remove_entities(hass, [light])
    assert_entity_counts(hass, Platform.SWITCH, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 2, 1)


async def test_switch_setup_no_perm(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    doorbell: Camera,
):
    """Test switch entity setup for light devices."""

    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict({"rawPermission": "light:read:*"})
    ]

    await init_entry(hass, ufp, [light, doorbell])

    assert_entity_counts(hass, Platform.SWITCH, 0, 0)


async def test_switch_setup_light(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
):
    """Test switch entity setup for light devices."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 2, 1)

    entity_registry = er.async_get(hass)

    description = LIGHT_SWITCHES[1]

    unique_id, entity_id = ids_from_device_description(
        Platform.SWITCH, light, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    description = LIGHT_SWITCHES[0]

    unique_id = f"{light.mac}_{description.key}"
    entity_id = f"switch.test_light_{description.name.lower().replace(' ', '_')}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_setup_camera_all(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
):
    """Test switch entity setup for camera devices (all enabled feature flags)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)

    entity_registry = er.async_get(hass)

    for description in CAMERA_SWITCHES_BASIC:
        unique_id, entity_id = ids_from_device_description(
            Platform.SWITCH, doorbell, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    description = CAMERA_SWITCHES[0]

    description_entity_name = (
        description.name.lower().replace(":", "").replace(" ", "_")
    )
    unique_id = f"{doorbell.mac}_{description.key}"
    entity_id = f"switch.test_camera_{description_entity_name}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_setup_camera_none(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
):
    """Test switch entity setup for camera devices (no enabled feature flags)."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SWITCH, 6, 5)

    entity_registry = er.async_get(hass)

    for description in CAMERA_SWITCHES_BASIC:
        if description.ufp_required_field is not None:
            continue

        unique_id, entity_id = ids_from_device_description(
            Platform.SWITCH, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    description = CAMERA_SWITCHES[0]

    description_entity_name = (
        description.name.lower().replace(":", "").replace(" ", "_")
    )
    unique_id = f"{camera.mac}_{description.key}"
    entity_id = f"switch.test_camera_{description_entity_name}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_light_status(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
):
    """Tests status light switch for lights."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 2, 1)

    description = LIGHT_SWITCHES[1]

    light.__fields__["set_status_light"] = Mock()
    light.set_status_light = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, light, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    light.set_status_light.assert_called_once_with(True)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    light.set_status_light.assert_called_with(False)


async def test_switch_camera_ssh(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
):
    """Tests SSH switch for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)

    description = CAMERA_SWITCHES[0]

    doorbell.__fields__["set_ssh"] = Mock()
    doorbell.set_ssh = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)
    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_ssh.assert_called_once_with(True)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_ssh.assert_called_with(False)


@pytest.mark.parametrize("description", CAMERA_SWITCHES_NO_EXTRA)
async def test_switch_camera_simple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    description: ProtectSwitchEntityDescription,
):
    """Tests all simple switches for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)

    assert description.ufp_set_method is not None

    doorbell.__fields__[description.ufp_set_method] = Mock()
    setattr(doorbell, description.ufp_set_method, AsyncMock())
    set_method = getattr(doorbell, description.ufp_set_method)

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    set_method.assert_called_once_with(True)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    set_method.assert_called_with(False)


async def test_switch_camera_highfps(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
):
    """Tests High FPS switch for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)

    description = CAMERA_SWITCHES[3]

    doorbell.__fields__["set_video_mode"] = Mock()
    doorbell.set_video_mode = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_video_mode.assert_called_once_with(VideoMode.HIGH_FPS)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_video_mode.assert_called_with(VideoMode.DEFAULT)


async def test_switch_camera_privacy(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
):
    """Tests Privacy Mode switch for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)

    description = CAMERA_SWITCHES[4]

    doorbell.__fields__["set_privacy"] = Mock()
    doorbell.set_privacy = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_privacy.assert_called_once_with(True, 0, RecordingMode.NEVER)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_privacy.assert_called_with(
        False, doorbell.mic_volume, doorbell.recording_settings.mode
    )


async def test_switch_camera_privacy_already_on(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
):
    """Tests Privacy Mode switch for cameras with privacy mode defaulted on."""

    doorbell.add_privacy_zone()
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 13, 12)

    description = CAMERA_SWITCHES[4]

    doorbell.__fields__["set_privacy"] = Mock()
    doorbell.set_privacy = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_privacy.assert_called_once_with(False, 100, RecordingMode.ALWAYS)
