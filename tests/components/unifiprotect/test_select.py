"""Test the UniFi Protect select platform."""

from __future__ import annotations

from copy import copy
from unittest.mock import AsyncMock, Mock

from pyunifiprotect.data import (
    Camera,
    DoorbellMessageType,
    IRLEDMode,
    LCDMessage,
    Light,
    LightModeEnableType,
    LightModeType,
    Liveview,
    RecordingMode,
    Viewer,
)
from pyunifiprotect.data.nvr import DoorbellMessage

from homeassistant.components.select import ATTR_OPTIONS
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.select import (
    CAMERA_SELECTS,
    LIGHT_MODE_OFF,
    LIGHT_SELECTS,
    VIEWER_SELECTS,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, ATTR_OPTION, Platform
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


async def test_select_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SELECT, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)


async def test_select_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SELECT, 2, 2)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SELECT, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SELECT, 2, 2)


async def test_select_viewer_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, viewer: Viewer
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 1, 1)
    await remove_entities(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 0, 0)
    await adopt_devices(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 1, 1)


async def test_select_setup_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test select entity setup for light devices."""

    light.light_mode_settings.enable_at = LightModeEnableType.DARK
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SELECT, 2, 2)

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
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    viewer: Viewer,
    liveview: Liveview,
) -> None:
    """Test select entity setup for light devices."""

    ufp.api.bootstrap.liveviews = {liveview.id: liveview}
    await init_entry(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 1, 1)

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
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test select entity setup for camera devices (all features)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    expected_values = (
        "Always",
        "Auto",
        "Default Message (Welcome)",
        "None",
        "Always Off",
    )

    for index, description in enumerate(CAMERA_SELECTS):
        unique_id, entity_id = ids_from_device_description(
            Platform.SELECT, doorbell, description
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
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test select entity setup for camera devices (no features)."""

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SELECT, 2, 2)

    expected_values = ("Always", "Auto", "Default Message (Welcome)")

    for index, description in enumerate(CAMERA_SELECTS):
        if index == 2:
            return

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


async def test_select_update_liveview(
    hass: HomeAssistant, ufp: MockUFPFixture, viewer: Viewer, liveview: Liveview
) -> None:
    """Test select entity update (new Liveview)."""

    ufp.api.bootstrap.liveviews = {liveview.id: liveview}
    await init_entry(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 1, 1)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, viewer, VIEWER_SELECTS[0]
    )

    state = hass.states.get(entity_id)
    assert state
    expected_options = state.attributes[ATTR_OPTIONS]

    new_liveview = copy(liveview)
    new_liveview.id = "test_id"

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_liveview

    ufp.api.bootstrap.liveviews = {
        **ufp.api.bootstrap.liveviews,
        new_liveview.id: new_liveview,
    }
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_OPTIONS] == expected_options


async def test_select_update_doorbell_settings(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test select entity update (new Doorbell Message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    expected_length = len(ufp.api.bootstrap.nvr.doorbell_settings.all_messages) + 1

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    state = hass.states.get(entity_id)
    assert state
    assert len(state.attributes[ATTR_OPTIONS]) == expected_length

    expected_length += 1
    new_nvr = copy(ufp.api.bootstrap.nvr)
    new_nvr.__fields__["update_all_messages"] = Mock(final=False)
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

    ufp.api.bootstrap.nvr = new_nvr
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    new_nvr.update_all_messages.assert_called_once()

    state = hass.states.get(entity_id)
    assert state
    assert len(state.attributes[ATTR_OPTIONS]) == expected_length


async def test_select_update_doorbell_message(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test select entity update (change doorbell message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Default Message (Welcome)"

    new_camera = doorbell.copy()
    new_camera.lcd_message = LCDMessage(
        type=DoorbellMessageType.CUSTOM_MESSAGE, text="Test"
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Test"


async def test_select_set_option_light_motion(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test Light Mode select."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SELECT, 2, 2)

    _, entity_id = ids_from_device_description(Platform.SELECT, light, LIGHT_SELECTS[0])

    light.__fields__["set_light_settings"] = Mock(final=False)
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
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, camera: Camera
) -> None:
    """Test Paired Camera select."""

    await init_entry(hass, ufp, [light, camera])
    assert_entity_counts(hass, Platform.SELECT, 4, 4)

    _, entity_id = ids_from_device_description(Platform.SELECT, light, LIGHT_SELECTS[1])

    light.__fields__["set_paired_camera"] = Mock(final=False)
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
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Recording Mode select."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[0]
    )

    doorbell.__fields__["set_recording_mode"] = Mock(final=False)
    doorbell.set_recording_mode = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Never"},
        blocking=True,
    )

    doorbell.set_recording_mode.assert_called_once_with(RecordingMode.NEVER)


async def test_select_set_option_camera_ir(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Infrared Mode select."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[1]
    )

    doorbell.__fields__["set_ir_led_model"] = Mock(final=False)
    doorbell.set_ir_led_model = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Always Enable"},
        blocking=True,
    )

    doorbell.set_ir_led_model.assert_called_once_with(IRLEDMode.ON)


async def test_select_set_option_camera_doorbell_custom(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Doorbell Text select (user defined message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    doorbell.__fields__["set_lcd_text"] = Mock(final=False)
    doorbell.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Test"},
        blocking=True,
    )

    doorbell.set_lcd_text.assert_called_once_with(
        DoorbellMessageType.CUSTOM_MESSAGE, text="Test"
    )


async def test_select_set_option_camera_doorbell_unifi(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Doorbell Text select (unifi message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    doorbell.__fields__["set_lcd_text"] = Mock(final=False)
    doorbell.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "LEAVE PACKAGE AT DOOR",
        },
        blocking=True,
    )

    doorbell.set_lcd_text.assert_called_once_with(
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

    doorbell.set_lcd_text.assert_called_with(None)


async def test_select_set_option_camera_doorbell_default(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Doorbell Text select (default message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    doorbell.__fields__["set_lcd_text"] = Mock(final=False)
    doorbell.set_lcd_text = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "Default Message (Welcome)",
        },
        blocking=True,
    )

    doorbell.set_lcd_text.assert_called_once_with(None)


async def test_select_set_option_viewer(
    hass: HomeAssistant, ufp: MockUFPFixture, viewer: Viewer, liveview: Liveview
) -> None:
    """Test Liveview select."""

    ufp.api.bootstrap.liveviews = {liveview.id: liveview}
    await init_entry(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 1, 1)

    _, entity_id = ids_from_device_description(
        Platform.SELECT, viewer, VIEWER_SELECTS[0]
    )

    viewer.__fields__["set_liveview"] = Mock(final=False)
    viewer.set_liveview = AsyncMock()

    liveview = list(viewer.api.bootstrap.liveviews.values())[0]

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: liveview.name},
        blocking=True,
    )

    viewer.set_liveview.assert_called_once_with(liveview)
