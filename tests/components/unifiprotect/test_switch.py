"""Test the UniFi Protect switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import Camera, Light, Permission, RecordingMode, VideoMode

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.switch import (
    ATTR_PREV_MIC,
    ATTR_PREV_RECORD,
    CAMERA_SWITCHES,
    LIGHT_SWITCHES,
    PRIVACY_MODE_SWITCH,
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
    if (
        not d.name.startswith("Detections:")
        and d.name
        not in {"SSH enabled", "Color night vision", "Tracking: person", "HDR mode"}
    )
    or d.name
    in {
        "Detections: motion",
        "Detections: person",
        "Detections: vehicle",
        "Detections: animal",
    }
]
CAMERA_SWITCHES_NO_EXTRA = [
    d
    for d in CAMERA_SWITCHES_BASIC
    if d.name not in ("High FPS", "Privacy mode", "HDR mode")
]


async def test_switch_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 2, 2)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)


async def test_switch_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 2, 2)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)


async def test_switch_nvr(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test switch entity setup for light devices."""

    await init_entry(hass, ufp, [])

    assert_entity_counts(hass, Platform.SWITCH, 2, 2)

    nvr = ufp.api.bootstrap.nvr
    nvr.__fields__["set_insights"] = Mock(final=False)
    nvr.set_insights = AsyncMock()
    entity_id = "switch.unifiprotect_insights_enabled"

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    nvr.set_insights.assert_called_once_with(True)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    nvr.set_insights.assert_called_with(False)


async def test_switch_setup_no_perm(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    doorbell: Camera,
) -> None:
    """Test switch entity setup for light devices."""

    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict({"rawPermission": "light:read:*"})
    ]

    await init_entry(hass, ufp, [light, doorbell])

    assert_entity_counts(hass, Platform.SWITCH, 0, 0)


async def test_switch_setup_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test switch entity setup for light devices."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)

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
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test switch entity setup for camera devices (all enabled feature flags)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

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
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test switch entity setup for camera devices (no enabled feature flags)."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SWITCH, 8, 7)

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
) -> None:
    """Tests status light switch for lights."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)

    description = LIGHT_SWITCHES[1]

    light.__fields__["set_status_light"] = Mock(final=False)
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
) -> None:
    """Tests SSH switch for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = CAMERA_SWITCHES[0]

    doorbell.__fields__["set_ssh"] = Mock(final=False)
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
) -> None:
    """Tests all simple switches for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    assert description.ufp_set_method is not None

    doorbell.__fields__[description.ufp_set_method] = Mock(final=False)
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
) -> None:
    """Tests High FPS switch for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = CAMERA_SWITCHES[3]

    doorbell.__fields__["set_video_mode"] = Mock(final=False)
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
) -> None:
    """Tests Privacy Mode switch for cameras with privacy mode defaulted on."""

    previous_mic = doorbell.mic_volume = 53
    previous_record = doorbell.recording_settings.mode = RecordingMode.DETECTIONS

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = PRIVACY_MODE_SWITCH

    doorbell.__fields__["set_privacy"] = Mock(final=False)
    doorbell.set_privacy = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)

    state = hass.states.get(entity_id)
    assert state and state.state == "off"
    assert ATTR_PREV_MIC not in state.attributes
    assert ATTR_PREV_RECORD not in state.attributes

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_privacy.assert_called_with(True, 0, RecordingMode.NEVER)

    new_doorbell = doorbell.copy()
    new_doorbell.add_privacy_zone()
    new_doorbell.mic_volume = 0
    new_doorbell.recording_settings.mode = RecordingMode.NEVER
    ufp.api.bootstrap.cameras = {new_doorbell.id: new_doorbell}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_doorbell
    ufp.ws_msg(mock_msg)

    state = hass.states.get(entity_id)
    assert state and state.state == "on"
    assert state.attributes[ATTR_PREV_MIC] == previous_mic
    assert state.attributes[ATTR_PREV_RECORD] == previous_record.value

    doorbell.set_privacy.reset_mock()

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_privacy.assert_called_with(False, previous_mic, previous_record)


async def test_switch_camera_privacy_already_on(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Tests Privacy Mode switch for cameras with privacy mode defaulted on."""

    doorbell.add_privacy_zone()
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = PRIVACY_MODE_SWITCH

    doorbell.__fields__["set_privacy"] = Mock(final=False)
    doorbell.set_privacy = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, doorbell, description)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    doorbell.set_privacy.assert_called_once_with(False, 100, RecordingMode.ALWAYS)
