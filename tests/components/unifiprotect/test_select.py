"""Test the UniFi Protect select platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect.data import Camera, Light
from pyunifiprotect.data.devices import LCDMessage, Viewer
from pyunifiprotect.data.nvr import DoorbellMessage, Liveview
from pyunifiprotect.data.types import (
    DoorbellMessageType,
    IRLEDMode,
    LightModeEnableType,
    LightModeType,
    RecordingMode,
)

from homeassistant.components.select.const import ATTR_OPTIONS
from homeassistant.components.unifiprotect.const import (
    ATTR_DURATION,
    ATTR_MESSAGE,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.components.unifiprotect.select import (
    CAMERA_SELECTS,
    LIGHT_MODE_OFF,
    LIGHT_SELECTS,
    SERVICE_SET_DOORBELL_MESSAGE,
    VIEWER_SELECTS,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    ids_from_device_description,
)


@pytest.fixture(name="viewer")
async def viewer_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_viewer: Viewer,
    mock_liveview: Liveview,
):
    """Fixture for a single viewport for testing the select platform."""

    # disable pydantic validation so mocking can happen
    Viewer.__config__.validate_assignment = False

    viewer_obj = mock_viewer.copy(deep=True)
    viewer_obj._api = mock_entry.api
    viewer_obj.name = "Test Viewer"
    viewer_obj.liveview_id = mock_liveview.id

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.viewers = {
        viewer_obj.id: viewer_obj,
    }
    mock_entry.api.bootstrap.liveviews = {mock_liveview.id: mock_liveview}

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SELECT, 1, 1)

    yield viewer_obj

    Viewer.__config__.validate_assignment = True


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the select platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_lcd_screen = True
    camera_obj.feature_flags.has_chime = True
    camera_obj.recording_settings.mode = RecordingMode.ALWAYS
    camera_obj.isp_settings.ir_led_mode = IRLEDMode.AUTO
    camera_obj.lcd_message = None
    camera_obj.chime_duration = 0

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SELECT, 4, 4)

    yield camera_obj

    Camera.__config__.validate_assignment = True


@pytest.fixture(name="light")
async def light_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_light: Light,
    camera: Camera,
):
    """Fixture for a single light for testing the select platform."""

    # disable pydantic validation so mocking can happen
    Light.__config__.validate_assignment = False

    light_obj = mock_light.copy(deep=True)
    light_obj._api = mock_entry.api
    light_obj.name = "Test Light"
    light_obj.camera_id = None
    light_obj.light_mode_settings.mode = LightModeType.MOTION
    light_obj.light_mode_settings.enable_at = LightModeEnableType.DARK

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {camera.id: camera}
    mock_entry.api.bootstrap.lights = {
        light_obj.id: light_obj,
    }

    await hass.config_entries.async_reload(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SELECT, 6, 6)

    yield light_obj

    Light.__config__.validate_assignment = True


@pytest.fixture(name="camera_none")
async def camera_none_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the select platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_lcd_screen = False
    camera_obj.feature_flags.has_chime = False
    camera_obj.recording_settings.mode = RecordingMode.ALWAYS
    camera_obj.isp_settings.ir_led_mode = IRLEDMode.AUTO

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SELECT, 2, 2)

    yield camera_obj

    Camera.__config__.validate_assignment = True


async def test_select_setup_light(
    hass: HomeAssistant,
    light: Light,
):
    """Test select entity setup for light devices."""

    entity_registry = er.async_get(hass)
    expected_values = ("On Motion - When Dark", "Not Paired")

    for index, description in enumerate(LIGHT_SELECTS):
        unique_id, entity_id = ids_from_device_description(
            Platform.SELECT, light, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_select_setup_viewer(
    hass: HomeAssistant,
    viewer: Viewer,
):
    """Test select entity setup for light devices."""

    entity_registry = er.async_get(hass)
    description = VIEWER_SELECTS[0]

    unique_id, entity_id = ids_from_device_description(
        Platform.SELECT, viewer, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == viewer.liveview.name
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_select_setup_camera_all(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test select entity setup for camera devices (all features)."""

    entity_registry = er.async_get(hass)
    expected_values = ("Always", "Auto", "Default Message (Welcome)", "None")

    for index, description in enumerate(CAMERA_SELECTS):
        unique_id, entity_id = ids_from_device_description(
            Platform.SELECT, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_select_setup_camera_none(
    hass: HomeAssistant,
    camera_none: Camera,
):
    """Test select entity setup for camera devices (no features)."""

    entity_registry = er.async_get(hass)
    expected_values = ("Always", "Auto", "Default Message (Welcome)")

    for index, description in enumerate(CAMERA_SELECTS):
        if index == 2:
            return

        unique_id, entity_id = ids_from_device_description(
            Platform.SELECT, camera_none, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_select_update_liveview(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    viewer: Viewer,
    mock_liveview: Liveview,
):
    """Test select entity update (new Liveview)."""

    _, entity_id = ids_from_device_description(
        Platform.SELECT, viewer, VIEWER_SELECTS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    expected_options = state.attributes[ATTR_OPTIONS]

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_liveview = copy(mock_liveview)
    new_liveview.id = "test_id"

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_liveview

    new_bootstrap.liveviews = {**new_bootstrap.liveviews, new_liveview.id: new_liveview}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_OPTIONS] == expected_options


async def test_select_update_doorbell_settings(
    hass: HomeAssistant, mock_entry: MockEntityFixture, camera: Camera
):
    """Test select entity update (new Doorbell Message)."""

    expected_length = (
        len(mock_entry.api.bootstrap.nvr.doorbell_settings.all_messages) + 1
    )

    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    state = hass.states.get(entity_id)
    assert state
    assert len(state.attributes[ATTR_OPTIONS]) == expected_length

    expected_length += 1
    new_nvr = copy(mock_entry.api.bootstrap.nvr)
    new_nvr.__fields__["update_all_messages"] = Mock()
    new_nvr.update_all_messages = Mock()

    new_nvr.doorbell_settings.all_messages = [
        *new_nvr.doorbell_settings.all_messages,
        DoorbellMessage(
            type=DoorbellMessageType.CUSTOM_MESSAGE,
            text="Test2",
        ),
    ]

    mock_msg = Mock()
    mock_msg.changed_data = {"doorbell_settings": {}}
    mock_msg.new_obj = new_nvr

    mock_entry.api.bootstrap.nvr = new_nvr
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    new_nvr.update_all_messages.assert_called_once()

    state = hass.states.get(entity_id)
    assert state
    assert len(state.attributes[ATTR_OPTIONS]) == expected_length


async def test_select_update_doorbell_message(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: Camera,
):
    """Test select entity update (change doorbell message)."""

    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Default Message (Welcome)"

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera.copy()
    new_camera.lcd_message = LCDMessage(
        type=DoorbellMessageType.CUSTOM_MESSAGE, text="Test"
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Test"


async def test_select_set_option_light_motion(
    hass: HomeAssistant,
    light: Light,
):
    """Test Light Mode select."""
    _, entity_id = ids_from_device_description(Platform.SELECT, light, LIGHT_SELECTS[0])

    light.__fields__["set_light_settings"] = Mock()
    light.set_light_settings = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LIGHT_MODE_OFF},
        blocking=True,
    )

    light.set_light_settings.assert_called_once_with(
        LightModeType.MANUAL, enable_at=None
    )


async def test_select_set_option_light_camera(
    hass: HomeAssistant,
    light: Light,
):
    """Test Paired Camera select."""
    _, entity_id = ids_from_device_description(Platform.SELECT, light, LIGHT_SELECTS[1])

    light.__fields__["set_paired_camera"] = Mock()
    light.set_paired_camera = AsyncMock()

    camera = list(light.api.bootstrap.cameras.values())[0]

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: camera.name},
        blocking=True,
    )

    light.set_paired_camera.assert_called_once_with(camera)

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Not Paired"},
        blocking=True,
    )

    light.set_paired_camera.assert_called_with(None)


async def test_select_set_option_camera_recording(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Recording Mode select."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[0]
    )

    camera.__fields__["set_recording_mode"] = Mock()
    camera.set_recording_mode = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Never"},
        blocking=True,
    )

    camera.set_recording_mode.assert_called_once_with(RecordingMode.NEVER)


async def test_select_set_option_camera_ir(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Infrared Mode select."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[1]
    )

    camera.__fields__["set_ir_led_model"] = Mock()
    camera.set_ir_led_model = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Always Enable"},
        blocking=True,
    )

    camera.set_ir_led_model.assert_called_once_with(IRLEDMode.ON)


async def test_select_set_option_camera_doorbell_custom(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Doorbell Text select (user defined message)."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    camera.__fields__["set_lcd_text"] = Mock()
    camera.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Test"},
        blocking=True,
    )

    camera.set_lcd_text.assert_called_once_with(
        DoorbellMessageType.CUSTOM_MESSAGE, text="Test"
    )


async def test_select_set_option_camera_doorbell_unifi(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Doorbell Text select (unifi message)."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    camera.__fields__["set_lcd_text"] = Mock()
    camera.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "LEAVE PACKAGE AT DOOR",
        },
        blocking=True,
    )

    camera.set_lcd_text.assert_called_once_with(
        DoorbellMessageType.LEAVE_PACKAGE_AT_DOOR
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "Default Message (Welcome)",
        },
        blocking=True,
    )

    camera.set_lcd_text.assert_called_with(None)


async def test_select_set_option_camera_doorbell_default(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Doorbell Text select (default message)."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    camera.__fields__["set_lcd_text"] = Mock()
    camera.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "Default Message (Welcome)",
        },
        blocking=True,
    )

    camera.set_lcd_text.assert_called_once_with(None)


async def test_select_set_option_viewer(
    hass: HomeAssistant,
    viewer: Viewer,
):
    """Test Liveview select."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, viewer, VIEWER_SELECTS[0]
    )

    viewer.__fields__["set_liveview"] = Mock()
    viewer.set_liveview = AsyncMock()

    liveview = list(viewer.api.bootstrap.liveviews.values())[0]

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: liveview.name},
        blocking=True,
    )

    viewer.set_liveview.assert_called_once_with(liveview)


async def test_select_service_doorbell_invalid(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Doorbell Text service (invalid)."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[1]
    )

    camera.__fields__["set_lcd_text"] = Mock()
    camera.set_lcd_text = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "unifiprotect",
            SERVICE_SET_DOORBELL_MESSAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_MESSAGE: "Test"},
            blocking=True,
        )

    assert not camera.set_lcd_text.called


async def test_select_service_doorbell_success(
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Doorbell Text service (success)."""
    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    camera.__fields__["set_lcd_text"] = Mock()
    camera.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "unifiprotect",
        SERVICE_SET_DOORBELL_MESSAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "Test",
        },
        blocking=True,
    )

    camera.set_lcd_text.assert_called_once_with(
        DoorbellMessageType.CUSTOM_MESSAGE, "Test", reset_at=None
    )


@patch("homeassistant.components.unifiprotect.select.utcnow")
async def test_select_service_doorbell_with_reset(
    mock_now,
    hass: HomeAssistant,
    camera: Camera,
):
    """Test Doorbell Text service (success with reset time)."""
    now = utcnow()
    mock_now.return_value = now

    _, entity_id = ids_from_device_description(
        Platform.SELECT, camera, CAMERA_SELECTS[2]
    )

    camera.__fields__["set_lcd_text"] = Mock()
    camera.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "unifiprotect",
        SERVICE_SET_DOORBELL_MESSAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "Test",
            ATTR_DURATION: 60,
        },
        blocking=True,
    )

    camera.set_lcd_text.assert_called_once_with(
        DoorbellMessageType.CUSTOM_MESSAGE,
        "Test",
        reset_at=now + timedelta(minutes=60),
    )
