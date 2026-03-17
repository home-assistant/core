"""Test the UniFi Protect select platform."""

from __future__ import annotations

from copy import copy
from unittest.mock import AsyncMock, Mock

from uiprotect.data import (
    Camera,
    DoorbellMessageType,
    IRLEDMode,
    LCDMessage,
    Light,
    LightModeEnableType,
    LightModeType,
    Liveview,
    PTZPatrol,
    RecordingMode,
    Viewer,
)
from uiprotect.data.nvr import DoorbellMessage

from homeassistant.components.select import ATTR_OPTIONS
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.select import (
    CAMERA_SELECTS,
    LIGHT_MODE_OFF,
    LIGHT_SELECTS,
    PTZ_PATROL_STOP,
    VIEWER_SELECTS,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import patch_ufp_method
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

    expected_values = ("motion_dark", "Not Paired")

    for index, description in enumerate(LIGHT_SELECTS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SELECT, light, description
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

    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, viewer, description
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
        "always",
        "auto",
        "Default Message (Welcome)",
        "none",
        "off",
    )

    for index, description in enumerate(CAMERA_SELECTS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SELECT, doorbell, description
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

    expected_values = ("always", "auto", "Default Message (Welcome)")

    for index, description in enumerate(CAMERA_SELECTS):
        if index == 2:
            return

        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SELECT, camera, description
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

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, viewer, VIEWER_SELECTS[0]
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

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    state = hass.states.get(entity_id)
    assert state
    assert len(state.attributes[ATTR_OPTIONS]) == expected_length

    expected_length += 1
    new_nvr = copy(ufp.api.bootstrap.nvr)

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

    with patch_ufp_method(new_nvr, "update_all_messages") as mock_method:
        ufp.api.bootstrap.nvr = new_nvr
        ufp.ws_msg(mock_msg)
        await hass.async_block_till_done()

        mock_method.assert_called_once()

    state = hass.states.get(entity_id)
    assert state
    assert len(state.attributes[ATTR_OPTIONS]) == expected_length


async def test_select_update_doorbell_message(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test select entity update (change doorbell message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Default Message (Welcome)"

    new_camera = doorbell.model_copy()
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

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, light, LIGHT_SELECTS[0]
    )

    with patch_ufp_method(
        light, "set_light_settings", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: LIGHT_MODE_OFF},
            blocking=True,
        )

        mock_method.assert_called_once_with(LightModeType.MANUAL, enable_at=None)


async def test_select_set_option_light_camera(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, camera: Camera
) -> None:
    """Test Paired Camera select."""

    await init_entry(hass, ufp, [light, camera])
    assert_entity_counts(hass, Platform.SELECT, 4, 4)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, light, LIGHT_SELECTS[1]
    )

    camera = list(light.api.bootstrap.cameras.values())[0]

    with patch_ufp_method(
        light, "set_paired_camera", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: camera.name},
            blocking=True,
        )

        mock_method.assert_called_once_with(camera)

        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Not Paired"},
            blocking=True,
        )

        mock_method.assert_called_with(None)


async def test_select_set_option_camera_recording(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Recording Mode select."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[0]
    )

    with patch_ufp_method(
        doorbell, "set_recording_mode", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "never"},
            blocking=True,
        )

        mock_method.assert_called_once_with(RecordingMode.NEVER)


async def test_select_set_option_camera_ir(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Infrared Mode select."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[1]
    )

    with patch_ufp_method(
        doorbell, "set_ir_led_model", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "on"},
            blocking=True,
        )

        mock_method.assert_called_once_with(IRLEDMode.ON)


async def test_select_set_option_camera_doorbell_custom(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Doorbell Text select (user defined message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    with patch_ufp_method(
        doorbell, "set_lcd_text", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Test"},
            blocking=True,
        )

        mock_method.assert_called_once_with(
            DoorbellMessageType.CUSTOM_MESSAGE, text="Test"
        )


async def test_select_set_option_camera_doorbell_unifi(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Doorbell Text select (unifi message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    with patch_ufp_method(
        doorbell, "set_lcd_text", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: "LEAVE PACKAGE AT DOOR",
            },
            blocking=True,
        )

        mock_method.assert_called_once_with(DoorbellMessageType.LEAVE_PACKAGE_AT_DOOR)

        await hass.services.async_call(
            "select",
            "select_option",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: "Default Message (Welcome)",
            },
            blocking=True,
        )

        mock_method.assert_called_with(None)


async def test_select_set_option_camera_doorbell_default(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test Doorbell Text select (default message)."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SELECT, 5, 5)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, doorbell, CAMERA_SELECTS[2]
    )

    with patch_ufp_method(
        doorbell, "set_lcd_text", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: "Default Message (Welcome)",
            },
            blocking=True,
        )

        mock_method.assert_called_once_with(None)


async def test_select_set_option_viewer(
    hass: HomeAssistant, ufp: MockUFPFixture, viewer: Viewer, liveview: Liveview
) -> None:
    """Test Liveview select."""

    ufp.api.bootstrap.liveviews = {liveview.id: liveview}
    await init_entry(hass, ufp, [viewer])
    assert_entity_counts(hass, Platform.SELECT, 1, 1)

    _, entity_id = await ids_from_device_description(
        hass, Platform.SELECT, viewer, VIEWER_SELECTS[0]
    )

    liveview = list(viewer.api.bootstrap.liveviews.values())[0]

    with patch_ufp_method(
        viewer, "set_liveview", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: liveview.name},
            blocking=True,
        )

        mock_method.assert_called_once_with(liveview)


# --- PTZ Patrol Test Helpers ---


def _get_ptz_entity_id(hass: HomeAssistant, camera: Camera, key: str) -> str | None:
    """Get PTZ entity ID by unique_id from entity registry."""
    entity_registry = er.async_get(hass)
    unique_id = f"{camera.mac}_{key}"
    return entity_registry.async_get_entity_id(
        Platform.SELECT, "unifiprotect", unique_id
    )


def _make_patrols(camera_id: str) -> list[PTZPatrol]:
    """Create mock PTZ patrols."""
    return [
        PTZPatrol(
            id="patrol1",
            name="Patrol 1",
            slot=0,
            presets=[0, 1],
            presetDurationSeconds=10,
            camera=camera_id,
        ),
        PTZPatrol(
            id="patrol2",
            name="Patrol 2",
            slot=1,
            presets=[0],
            presetDurationSeconds=5,
            camera=camera_id,
        ),
    ]


async def _setup_ptz_camera(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
    *,
    patrols: list[PTZPatrol] | None = None,
) -> None:
    """Set up PTZ camera with mocked patrols."""
    ptz_camera.get_ptz_patrols.return_value = patrols or []
    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [ptz_camera])


# --- PTZ Patrol Tests ---


async def test_select_ptz_patrol_setup(
    hass: HomeAssistant, ufp: MockUFPFixture, ptz_camera: Camera
) -> None:
    """Test PTZ patrol select entity setup."""
    await _setup_ptz_camera(hass, ufp, ptz_camera, patrols=_make_patrols(ptz_camera.id))

    # PTZ camera should have 1 additional select entity (patrol)
    # Regular camera has 2 (recording_mode, infrared_mode), PTZ has 2 + 1 = 3
    assert_entity_counts(hass, Platform.SELECT, 3, 3)

    entity_id = _get_ptz_entity_id(hass, ptz_camera, "ptz_patrol")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == PTZ_PATROL_STOP
    options = state.attributes.get(ATTR_OPTIONS, [])
    assert options == ["stop", "Patrol 1", "Patrol 2"]


async def test_select_ptz_patrol_start(
    hass: HomeAssistant, ufp: MockUFPFixture, ptz_camera: Camera
) -> None:
    """Test starting a PTZ patrol."""
    await _setup_ptz_camera(
        hass, ufp, ptz_camera, patrols=_make_patrols(ptz_camera.id)[:1]
    )

    entity_id = _get_ptz_entity_id(hass, ptz_camera, "ptz_patrol")
    assert entity_id is not None
    with patch_ufp_method(
        ptz_camera, "ptz_patrol_start_public", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Patrol 1"},
            blocking=True,
        )
        mock_method.assert_called_once_with(slot=0)


async def test_select_ptz_patrol_stop(
    hass: HomeAssistant, ufp: MockUFPFixture, ptz_camera: Camera
) -> None:
    """Test stopping a PTZ patrol."""
    await _setup_ptz_camera(
        hass, ufp, ptz_camera, patrols=_make_patrols(ptz_camera.id)[:1]
    )

    entity_id = _get_ptz_entity_id(hass, ptz_camera, "ptz_patrol")
    assert entity_id is not None
    with patch_ufp_method(
        ptz_camera, "ptz_patrol_stop_public", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "stop"},
            blocking=True,
        )
        mock_method.assert_called_once()


async def test_select_ptz_patrol_active_state(
    hass: HomeAssistant, ufp: MockUFPFixture, ptz_camera: Camera
) -> None:
    """Test PTZ patrol shows active patrol from device state."""
    patrols = _make_patrols(ptz_camera.id)
    ptz_camera.active_patrol_slot = 0

    await _setup_ptz_camera(hass, ufp, ptz_camera, patrols=patrols)

    entity_id = _get_ptz_entity_id(hass, ptz_camera, "ptz_patrol")
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Patrol 1"


async def test_select_ptz_patrol_websocket_update(
    hass: HomeAssistant, ufp: MockUFPFixture, ptz_camera: Camera
) -> None:
    """Test PTZ patrol state updates via websocket."""
    patrols = _make_patrols(ptz_camera.id)
    await _setup_ptz_camera(hass, ufp, ptz_camera, patrols=patrols)

    entity_id = _get_ptz_entity_id(hass, ptz_camera, "ptz_patrol")
    assert entity_id is not None

    # Initially stopped
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == PTZ_PATROL_STOP

    # Simulate websocket update: patrol starts
    new_camera = ptz_camera.model_copy()
    new_camera.active_patrol_slot = 1

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Patrol 2"

    # Simulate websocket update: patrol stops
    new_camera2 = ptz_camera.model_copy()
    new_camera2.active_patrol_slot = None

    mock_msg2 = Mock()
    mock_msg2.changed_data = {}
    mock_msg2.new_obj = new_camera2

    ufp.api.bootstrap.cameras = {new_camera2.id: new_camera2}
    ufp.ws_msg(mock_msg2)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == PTZ_PATROL_STOP


async def test_select_ptz_camera_adopt(
    hass: HomeAssistant, ufp: MockUFPFixture, ptz_camera: Camera
) -> None:
    """Test adopting a new PTZ camera creates patrol entity."""
    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.SELECT, 0, 0)

    ptz_camera._api = ufp.api
    for channel in ptz_camera.channels:
        channel._api = ufp.api

    ptz_camera.get_ptz_patrols.return_value = _make_patrols(ptz_camera.id)

    await adopt_devices(hass, ufp, [ptz_camera])
    await hass.async_block_till_done()

    # Should have 2 regular camera selects + 1 patrol select = 3
    assert_entity_counts(hass, Platform.SELECT, 3, 3)

    patrol_entity_id = _get_ptz_entity_id(hass, ptz_camera, "ptz_patrol")
    assert patrol_entity_id is not None
