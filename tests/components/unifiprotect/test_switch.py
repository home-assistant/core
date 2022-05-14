"""Test the UniFi Protect switch platform."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera, Light
from pyunifiprotect.data.types import RecordingMode, SmartDetectObjectType, VideoMode

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.switch import (
    CAMERA_SWITCHES,
    LIGHT_SWITCHES,
    ProtectSwitchEntityDescription,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    enable_entity,
    ids_from_device_description,
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


@pytest.fixture(name="light")
async def light_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Fixture for a single light for testing the switch platform."""

    # disable pydantic validation so mocking can happen
    Light.__config__.validate_assignment = False

    light_obj = mock_light.copy(deep=True)
    light_obj._api = mock_entry.api
    light_obj.name = "Test Light"
    light_obj.is_ssh_enabled = False
    light_obj.light_device_settings.is_indicator_enabled = False

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.lights = {
        light_obj.id: light_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SWITCH, 2, 1)

    yield light_obj

    Light.__config__.validate_assignment = True


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the switch platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.recording_settings.mode = RecordingMode.DETECTIONS
    camera_obj.feature_flags.has_led_status = True
    camera_obj.feature_flags.has_hdr = True
    camera_obj.feature_flags.video_modes = [VideoMode.DEFAULT, VideoMode.HIGH_FPS]
    camera_obj.feature_flags.has_privacy_mask = True
    camera_obj.feature_flags.has_speaker = True
    camera_obj.feature_flags.has_smart_detect = True
    camera_obj.feature_flags.smart_detect_types = [
        SmartDetectObjectType.PERSON,
        SmartDetectObjectType.VEHICLE,
    ]
    camera_obj.is_ssh_enabled = False
    camera_obj.led_settings.is_enabled = False
    camera_obj.hdr_mode = False
    camera_obj.video_mode = VideoMode.DEFAULT
    camera_obj.remove_privacy_zone()
    camera_obj.speaker_settings.are_system_sounds_enabled = False
    camera_obj.osd_settings.is_name_enabled = False
    camera_obj.osd_settings.is_date_enabled = False
    camera_obj.osd_settings.is_logo_enabled = False
    camera_obj.osd_settings.is_debug_enabled = False
    camera_obj.smart_detect_settings.object_types = []

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SWITCH, 12, 11)

    yield camera_obj

    Camera.__config__.validate_assignment = True


@pytest.fixture(name="camera_none")
async def camera_none_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the switch platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.recording_settings.mode = RecordingMode.DETECTIONS
    camera_obj.feature_flags.has_led_status = False
    camera_obj.feature_flags.has_hdr = False
    camera_obj.feature_flags.video_modes = [VideoMode.DEFAULT]
    camera_obj.feature_flags.has_privacy_mask = False
    camera_obj.feature_flags.has_speaker = False
    camera_obj.feature_flags.has_smart_detect = False
    camera_obj.is_ssh_enabled = False
    camera_obj.osd_settings.is_name_enabled = False
    camera_obj.osd_settings.is_date_enabled = False
    camera_obj.osd_settings.is_logo_enabled = False
    camera_obj.osd_settings.is_debug_enabled = False

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SWITCH, 5, 4)

    yield camera_obj

    Camera.__config__.validate_assignment = True


@pytest.fixture(name="camera_privacy")
async def camera_privacy_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the switch platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.recording_settings.mode = RecordingMode.NEVER
    camera_obj.feature_flags.has_led_status = False
    camera_obj.feature_flags.has_hdr = False
    camera_obj.feature_flags.video_modes = [VideoMode.DEFAULT]
    camera_obj.feature_flags.has_privacy_mask = True
    camera_obj.feature_flags.has_speaker = False
    camera_obj.feature_flags.has_smart_detect = False
    camera_obj.add_privacy_zone()
    camera_obj.is_ssh_enabled = False
    camera_obj.osd_settings.is_name_enabled = False
    camera_obj.osd_settings.is_date_enabled = False
    camera_obj.osd_settings.is_logo_enabled = False
    camera_obj.osd_settings.is_debug_enabled = False

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SWITCH, 6, 5)

    yield camera_obj

    Camera.__config__.validate_assignment = True


async def test_switch_setup_light(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    light: Light,
):
    """Test switch entity setup for light devices."""

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

    unique_id = f"{light.id}_{description.key}"
    entity_id = f"switch.test_light_{description.name.lower().replace(' ', '_')}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_setup_camera_all(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: Camera,
):
    """Test switch entity setup for camera devices (all enabled feature flags)."""

    entity_registry = er.async_get(hass)

    for description in CAMERA_SWITCHES_BASIC:
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
    unique_id = f"{camera.id}_{description.key}"
    entity_id = f"switch.test_camera_{description_entity_name}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_setup_camera_none(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera_none: Camera,
):
    """Test switch entity setup for camera devices (no enabled feature flags)."""

    entity_registry = er.async_get(hass)

    for description in CAMERA_SWITCHES_BASIC:
        if description.ufp_required_field is not None:
            continue

        unique_id, entity_id = ids_from_device_description(
            Platform.SWITCH, camera_none, description
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
    unique_id = f"{camera_none.id}_{description.key}"
    entity_id = f"switch.test_camera_{description_entity_name}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_light_status(hass: HomeAssistant, light: Light):
    """Tests status light switch for lights."""

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
    hass: HomeAssistant, camera: Camera, mock_entry: MockEntityFixture
):
    """Tests SSH switch for cameras."""

    description = CAMERA_SWITCHES[0]

    camera.__fields__["set_ssh"] = Mock()
    camera.set_ssh = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, camera, description)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera.set_ssh.assert_called_once_with(True)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera.set_ssh.assert_called_with(False)


@pytest.mark.parametrize("description", CAMERA_SWITCHES_NO_EXTRA)
async def test_switch_camera_simple(
    hass: HomeAssistant, camera: Camera, description: ProtectSwitchEntityDescription
):
    """Tests all simple switches for cameras."""

    assert description.ufp_set_method is not None

    camera.__fields__[description.ufp_set_method] = Mock()
    setattr(camera, description.ufp_set_method, AsyncMock())
    set_method = getattr(camera, description.ufp_set_method)

    _, entity_id = ids_from_device_description(Platform.SWITCH, camera, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    set_method.assert_called_once_with(True)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    set_method.assert_called_with(False)


async def test_switch_camera_highfps(hass: HomeAssistant, camera: Camera):
    """Tests High FPS switch for cameras."""

    description = CAMERA_SWITCHES[3]

    camera.__fields__["set_video_mode"] = Mock()
    camera.set_video_mode = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, camera, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera.set_video_mode.assert_called_once_with(VideoMode.HIGH_FPS)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera.set_video_mode.assert_called_with(VideoMode.DEFAULT)


async def test_switch_camera_privacy(hass: HomeAssistant, camera: Camera):
    """Tests Privacy Mode switch for cameras."""

    description = CAMERA_SWITCHES[4]

    camera.__fields__["set_privacy"] = Mock()
    camera.set_privacy = AsyncMock()

    _, entity_id = ids_from_device_description(Platform.SWITCH, camera, description)

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera.set_privacy.assert_called_once_with(True, 0, RecordingMode.NEVER)

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera.set_privacy.assert_called_with(
        False, camera.mic_volume, camera.recording_settings.mode
    )


async def test_switch_camera_privacy_already_on(
    hass: HomeAssistant, camera_privacy: Camera
):
    """Tests Privacy Mode switch for cameras with privacy mode defaulted on."""

    description = CAMERA_SWITCHES[4]

    camera_privacy.__fields__["set_privacy"] = Mock()
    camera_privacy.set_privacy = AsyncMock()

    _, entity_id = ids_from_device_description(
        Platform.SWITCH, camera_privacy, description
    )

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    camera_privacy.set_privacy.assert_called_once_with(False, 100, RecordingMode.ALWAYS)
