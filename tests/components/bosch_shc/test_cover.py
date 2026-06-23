"""Tests for the Bosch SHC cover platform."""

from unittest.mock import AsyncMock, MagicMock

from boschshcpy import SHCShutterControl

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverState,
)
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STOPPED = SHCShutterControl.ShutterControlService.State.STOPPED
_MOVING = SHCShutterControl.ShutterControlService.State.MOVING
_OPENING = SHCShutterControl.ShutterControlService.State.OPENING
_CLOSING = SHCShutterControl.ShutterControlService.State.CLOSING


def _make_shutter(
    device_id: str = "shutter-1",
    name: str = "Test Shutter",
    device_model: str = "BBL",
    level: float = 1.0,
    operation_state=None,
) -> MagicMock:
    """Create a mock shutter-control device."""
    if operation_state is None:
        operation_state = _STOPPED
    device = make_device(
        device_id=device_id,
        name=name,
        device_model=device_model,
        level=level,
        operation_state=operation_state,
        status="AVAILABLE",
    )
    device.async_set_level = AsyncMock()
    device.async_stop = AsyncMock()
    return device


def _make_blind(
    device_id: str = "blind-1",
    name: str = "Test Blind",
    level: float = 0.5,
    current_angle: float = 0.25,
    operation_state=None,
) -> MagicMock:
    """Create a mock micromodule-blinds device."""
    if operation_state is None:
        operation_state = _STOPPED
    device = make_device(
        device_id=device_id,
        name=name,
        device_model="MICROMODULE_BLINDS",
        level=level,
        current_angle=current_angle,
        operation_state=operation_state,
        status="AVAILABLE",
    )
    device.async_set_level = AsyncMock()
    device.async_stop_blinds = AsyncMock()
    device.async_set_target_angle = AsyncMock()
    return device


# ---------------------------------------------------------------------------
# ShutterControlCover — BBL model (shutter_controls list)
# ---------------------------------------------------------------------------


async def test_shutter_bbl_open_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BBL shutter at level=1.0 + STOPPED → STATE_OPEN, position=100."""
    device = _make_shutter(level=1.0, operation_state=_STOPPED, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_shutter")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100
    assert state.attributes.get("device_class") == CoverDeviceClass.SHUTTER


async def test_shutter_bbl_closed_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BBL shutter at level=0.0 + STOPPED → STATE_CLOSED, position=0."""
    device = _make_shutter(level=0.0, operation_state=_STOPPED, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_shutter")
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_shutter_bbl_open_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """Calling open_cover calls async_set_level(1.0) on the device."""
    device = _make_shutter(level=0.0, operation_state=_STOPPED, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_OPEN_COVER,
        {"entity_id": "cover.test_shutter"},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(1.0)


async def test_shutter_bbl_close_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """Calling close_cover calls async_set_level(0.0) on the device."""
    device = _make_shutter(level=1.0, operation_state=_STOPPED, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_CLOSE_COVER,
        {"entity_id": "cover.test_shutter"},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(0.0)


async def test_shutter_bbl_stop_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """Calling stop_cover calls async_stop() on the device."""
    device = _make_shutter(level=0.5, operation_state=_MOVING, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_STOP_COVER,
        {"entity_id": "cover.test_shutter"},
        blocking=True,
    )

    device.async_stop.assert_awaited_once()


async def test_shutter_bbl_set_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """set_cover_position converts percentage → level fraction."""
    device = _make_shutter(level=1.0, operation_state=_STOPPED, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.test_shutter", ATTR_POSITION: 42},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(0.42)


async def test_shutter_bbl_operation_state_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """extra_state_attributes exposes operation_state."""
    device = _make_shutter(level=1.0, operation_state=_STOPPED, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_shutter")
    assert state is not None
    assert state.attributes.get("operation_state") == _STOPPED


# ---------------------------------------------------------------------------
# ShutterControlCover — OPENING / CLOSING operation states
# ---------------------------------------------------------------------------


async def test_shutter_opening_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """OPENING operation state → HA state is 'opening'."""
    device = _make_shutter(level=0.5, operation_state=_OPENING, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_shutter")
    assert state is not None
    assert state.state == CoverState.OPENING


async def test_shutter_closing_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """CLOSING operation state → HA state is 'closing'."""
    device = _make_shutter(level=0.5, operation_state=_CLOSING, device_model="BBL")
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_shutter")
    assert state is not None
    assert state.state == CoverState.CLOSING


# ---------------------------------------------------------------------------
# ShutterControlCover — MICROMODULE_SHUTTER model (micromodule_shutter_controls)
# ---------------------------------------------------------------------------


async def test_micromodule_shutter_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_SHUTTER device open via micromodule_shutter_controls list."""
    device = _make_shutter(
        device_id="mm-shutter-1",
        name="MM Shutter",
        device_model="MICROMODULE_SHUTTER",
        level=1.0,
        operation_state=_STOPPED,
    )
    # MICROMODULE_SHUTTER may have no physical keypad
    device._keypad_service = None
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.mm_shutter")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    await hass.services.async_call(
        "cover",
        SERVICE_OPEN_COVER,
        {"entity_id": "cover.mm_shutter"},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(1.0)


async def test_micromodule_shutter_stop_no_keypad(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_SHUTTER stop with no keypad service does not crash."""
    device = _make_shutter(
        device_id="mm-shutter-nkp",
        name="MM Shutter NKP",
        device_model="MICROMODULE_SHUTTER",
        level=0.5,
        operation_state=_MOVING,
    )
    device._keypad_service = None
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    # Should not raise even with no keypad service
    await hass.services.async_call(
        "cover",
        SERVICE_STOP_COVER,
        {"entity_id": "cover.mm_shutter_nkp"},
        blocking=True,
    )

    device.async_stop.assert_awaited_once()


async def test_micromodule_shutter_set_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """set_cover_position on MICROMODULE_SHUTTER records last_position and calls async_set_level."""
    device = _make_shutter(
        device_id="mm-shutter-pos",
        name="MM Shutter Pos",
        device_model="MICROMODULE_SHUTTER",
        level=0.8,
        operation_state=_STOPPED,
    )
    device._keypad_service = None
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.mm_shutter_pos", ATTR_POSITION: 60},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(0.60)


# ---------------------------------------------------------------------------
# ShutterControlCover — MICROMODULE_AWNING device_class
# ---------------------------------------------------------------------------


async def test_shutter_awning_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_AWNING model → device_class is 'awning'."""
    device = _make_shutter(
        device_id="awning-1",
        name="Test Awning",
        device_model="MICROMODULE_AWNING",
        level=1.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_awning")
    assert state is not None
    assert state.attributes.get("device_class") == CoverDeviceClass.AWNING


# ---------------------------------------------------------------------------
# BlindsControlCover — micromodule_blinds list
# ---------------------------------------------------------------------------


async def test_blinds_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BlindsControlCover always reports device_class = 'blind'."""
    device = _make_blind(level=0.5, current_angle=0.25, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_blind")
    assert state is not None
    assert state.attributes.get("device_class") == CoverDeviceClass.BLIND


async def test_blinds_position_and_tilt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BlindsControlCover reports correct position and tilt from level/current_angle."""
    # level=0.7 → position=70; current_angle=0.3 → tilt=round((1.0-0.3)*100)=70
    device = _make_blind(level=0.7, current_angle=0.3, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_blind")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 70


async def test_blinds_open_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """open_cover on blinds calls async_set_level(1.0)."""
    device = _make_blind(level=0.0, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_OPEN_COVER,
        {"entity_id": "cover.test_blind"},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(1.0)


async def test_blinds_close_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """close_cover on blinds calls async_set_level(0.0)."""
    device = _make_blind(level=1.0, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_CLOSE_COVER,
        {"entity_id": "cover.test_blind"},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(0.0)


async def test_blinds_stop_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """stop_cover on blinds calls async_stop_blinds() (not async_stop)."""
    device = _make_blind(level=0.5, operation_state=_MOVING)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_STOP_COVER,
        {"entity_id": "cover.test_blind"},
        blocking=True,
    )

    device.async_stop_blinds.assert_awaited_once()


async def test_blinds_set_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """set_cover_position on blinds calls async_set_level with fraction."""
    device = _make_blind(level=1.0, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.test_blind", ATTR_POSITION: 75},
        blocking=True,
    )

    device.async_set_level.assert_awaited_once_with(0.75)


async def test_blinds_open_tilt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """open_cover_tilt calls async_set_target_angle(0.0) (1.0 - 1.0)."""
    device = _make_blind(level=0.5, current_angle=0.5, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.test_blind"},
        blocking=True,
    )

    device.async_set_target_angle.assert_awaited_once_with(0.0)


async def test_blinds_close_tilt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """close_cover_tilt calls async_set_target_angle(1.0) (1.0 - 0.0)."""
    device = _make_blind(level=0.5, current_angle=0.0, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.test_blind"},
        blocking=True,
    )

    device.async_set_target_angle.assert_awaited_once_with(1.0)


async def test_blinds_set_tilt_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """set_cover_tilt_position converts tilt% → inverted angle fraction."""
    device = _make_blind(level=0.5, current_angle=0.0, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    # tilt=25 → target_angle = 1.0 - (25/100) = 0.75
    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.test_blind", ATTR_TILT_POSITION: 25},
        blocking=True,
    )

    device.async_set_target_angle.assert_awaited_once_with(0.75)


async def test_blinds_stop_tilt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """stop_cover_tilt calls async_stop_blinds()."""
    device = _make_blind(level=0.5, current_angle=0.5, operation_state=_MOVING)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        "stop_cover_tilt",
        {"entity_id": "cover.test_blind"},
        blocking=True,
    )

    device.async_stop_blinds.assert_awaited_once()


async def test_blinds_closed_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BlindsControlCover at level=0.0 + STOPPED → STATE_CLOSED."""
    device = _make_blind(level=0.0, current_angle=1.0, operation_state=_STOPPED)
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_blind")
    assert state is not None
    assert state.state == STATE_CLOSED


# ---------------------------------------------------------------------------
# Multiple devices coexist
# ---------------------------------------------------------------------------


async def test_multiple_covers_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """All three collections produce separate entities."""
    shutter = _make_shutter(
        device_id="shutter-1",
        name="Shutter One",
        device_model="BBL",
        level=1.0,
        operation_state=_STOPPED,
    )
    mm_shutter = _make_shutter(
        device_id="mm-shutter-2",
        name="Shutter Two",
        device_model="MICROMODULE_SHUTTER",
        level=0.5,
        operation_state=_STOPPED,
    )
    mm_shutter._keypad_service = None
    blind = _make_blind(
        device_id="blind-3",
        name="Blind Three",
        level=0.5,
        current_angle=0.0,
        operation_state=_STOPPED,
    )

    mock_device_helper.shutter_controls = [shutter]
    mock_device_helper.micromodule_shutter_controls = [mm_shutter]
    mock_device_helper.micromodule_blinds = [blind]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.shutter_one") is not None
    assert hass.states.get("cover.shutter_two") is not None
    assert hass.states.get("cover.blind_three") is not None


# ---------------------------------------------------------------------------
# device_excluded — shutter and blind skipped when in exclusion list
# ---------------------------------------------------------------------------


async def test_shutter_excluded_by_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """A shutter listed in excluded_devices options is not registered."""
    from homeassistant.components.bosch_shc.const import (  # noqa: PLC0415
        DOMAIN,
        OPT_EXCLUDED_DEVICES,
    )

    from tests.common import MockConfigEntry as _MCE  # noqa: PLC0415

    excluded_entry = _MCE(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data=mock_config_entry.data,
        options={OPT_EXCLUDED_DEVICES: ["shutter-1"]},
    )

    device = _make_shutter(
        device_id="shutter-1",
        name="Excluded Shutter",
        level=1.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, excluded_entry)

    assert hass.states.get("cover.excluded_shutter") is None


async def test_blind_excluded_by_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """A blind listed in excluded_devices options is not registered."""
    from homeassistant.components.bosch_shc.const import (  # noqa: PLC0415
        DOMAIN,
        OPT_EXCLUDED_DEVICES,
    )

    from tests.common import MockConfigEntry as _MCE  # noqa: PLC0415

    excluded_entry = _MCE(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data=mock_config_entry.data,
        options={OPT_EXCLUDED_DEVICES: ["blind-1"]},
    )

    device = _make_blind(
        device_id="blind-1",
        name="Excluded Blind",
        level=0.5,
        operation_state=_STOPPED,
    )
    mock_device_helper.micromodule_blinds = [device]

    await setup_integration(hass, excluded_entry)

    assert hass.states.get("cover.excluded_blind") is None


# ---------------------------------------------------------------------------
# MICROMODULE_SHUTTER with real keypad service — _micromodule_keypad_switch_off
# ---------------------------------------------------------------------------


async def test_micromodule_shutter_stop_with_keypad(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """stop_cover with a real keypad service sets eventtype and calls async_stop."""
    from boschshcpy import SHCMicromoduleShutterControl  # noqa: PLC0415

    device = _make_shutter(
        device_id="mm-shutter-kp",
        name="MM Shutter KP",
        device_model="MICROMODULE_SHUTTER",
        level=0.5,
        operation_state=_MOVING,
    )
    # Simulate a real keypad service being present (not None)
    device._keypad_service = MagicMock()
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "cover",
        SERVICE_STOP_COVER,
        {"entity_id": "cover.mm_shutter_kp"},
        blocking=True,
    )

    # The eventtype setter and async_stop must both have been called
    assert (
        device.eventtype
        == SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_OFF
    )
    device.async_stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# BBL MOVING state direction logic with last_position established
# ---------------------------------------------------------------------------


def _get_cover_callback(device: MagicMock, entity_id: str):
    """Return the update_entity_information callback registered for entity_id."""
    for call in device.subscribe_callback.call_args_list:
        if call[0][0] == entity_id:
            return call[0][1]
    raise AssertionError(
        f"No subscribe_callback found for entity_id '{entity_id}'. "
        f"Registered: {[c[0][0] for c in device.subscribe_callback.call_args_list]}"
    )


async def test_shutter_bbl_moving_opening_direction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BBL MOVING with target > last_position → is_opening=True (lines 136-141)."""
    # Start at STOPPED so _update_attr sets _last_position = 0 on init
    device = _make_shutter(
        device_id="bbl-moving-open",
        name="BBL Moving Open",
        device_model="BBL",
        level=0.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    # Now simulate device moving to 50% (opening from 0)
    device.level = 0.5
    device.operation_state = _MOVING

    # Trigger the entity's _update_attr via the cover entity's callback
    _get_cover_callback(device, "cover.bbl_moving_open")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.bbl_moving_open")
    assert state is not None
    assert state.state == CoverState.OPENING


async def test_shutter_bbl_moving_closing_direction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """BBL MOVING with target < last_position → is_closing=True (lines 136-141)."""
    device = _make_shutter(
        device_id="bbl-moving-close",
        name="BBL Moving Close",
        device_model="BBL",
        level=1.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    # Simulate moving to 30% (closing from 100)
    device.level = 0.3
    device.operation_state = _MOVING

    _get_cover_callback(device, "cover.bbl_moving_close")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.bbl_moving_close")
    assert state is not None
    assert state.state == CoverState.CLOSING


async def test_shutter_unknown_model_moving(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """Unknown model in MOVING state logs debug and sets direction to None (lines 183-188)."""
    device = _make_shutter(
        device_id="unknown-moving",
        name="Unknown Moving",
        device_model="UNKNOWN_MODEL",
        level=0.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    device.level = 0.5
    device.operation_state = _MOVING

    _get_cover_callback(device, "cover.unknown_moving")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.unknown_moving")
    assert state is not None
    # Direction should be unknown → HA state is 'open' (not closed) since level=0.5
    assert state.state == STATE_OPEN


async def test_shutter_micromodule_shutter_moving_keycode1(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_SHUTTER MOVING with keycode=1/SWITCH_ON → opening (lines 149-152)."""
    from boschshcpy import SHCMicromoduleShutterControl  # noqa: PLC0415

    device = _make_shutter(
        device_id="mm-kc1",
        name="MM KC1",
        device_model="MICROMODULE_SHUTTER",
        level=0.0,
        operation_state=_STOPPED,
    )
    device._keypad_service = None
    device.keycode = 1
    device.eventtype = (
        SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_ON
    )
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    device.operation_state = _MOVING
    device.level = 0.5

    _get_cover_callback(device, "cover.mm_kc1")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.mm_kc1")
    assert state is not None
    assert state.state == CoverState.OPENING


async def test_shutter_micromodule_shutter_moving_keycode2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_SHUTTER MOVING with keycode=2/SWITCH_ON → closing (lines 158-161)."""
    from boschshcpy import SHCMicromoduleShutterControl  # noqa: PLC0415

    device = _make_shutter(
        device_id="mm-kc2",
        name="MM KC2",
        device_model="MICROMODULE_SHUTTER",
        level=1.0,
        operation_state=_STOPPED,
    )
    device._keypad_service = None
    device.keycode = 2
    device.eventtype = (
        SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_ON
    )
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    device.operation_state = _MOVING
    device.level = 0.5

    _get_cover_callback(device, "cover.mm_kc2")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.mm_kc2")
    assert state is not None
    assert state.state == CoverState.CLOSING


async def test_shutter_micromodule_shutter_moving_app_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_SHUTTER MOVING via app-command (non-keycode) → direction from last_position (lines 163-170)."""
    from boschshcpy import SHCMicromoduleShutterControl  # noqa: PLC0415

    device = _make_shutter(
        device_id="mm-app",
        name="MM App",
        device_model="MICROMODULE_SHUTTER",
        level=0.0,
        operation_state=_STOPPED,
    )
    device._keypad_service = None
    device.keycode = 0
    device.eventtype = (
        SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_OFF
    )
    mock_device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    # Simulate app command: STOPPED first sets _last_position=0, then MOVING to 0.8
    device.operation_state = _MOVING
    device.level = 0.8

    _get_cover_callback(device, "cover.mm_app")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.mm_app")
    assert state is not None
    assert state.state == CoverState.OPENING


async def test_shutter_micromodule_blinds_moving_direction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """MICROMODULE_BLINDS MOVING with last_position → direction flag (lines 175-180)."""
    device = _make_shutter(
        device_id="mm-blinds-dir",
        name="MM Blinds Dir",
        device_model="MICROMODULE_BLINDS",
        level=1.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    # Close direction: level goes from 100 → 30
    device.operation_state = _MOVING
    device.level = 0.3

    _get_cover_callback(device, "cover.mm_blinds_dir")()
    await hass.async_block_till_done()

    state = hass.states.get("cover.mm_blinds_dir")
    assert state is not None
    assert state.state == CoverState.CLOSING


async def test_shutter_skip_update_branch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_device_helper: MagicMock,
) -> None:
    """After an HA command, the first STOPPED update is skipped (_skip_update branch, line 123)."""
    device = _make_shutter(
        device_id="skip-update",
        name="Skip Update",
        device_model="BBL",
        level=1.0,
        operation_state=_STOPPED,
    )
    mock_device_helper.shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    # Issue open_cover → sets _skip_update=True internally
    await hass.services.async_call(
        "cover",
        SERVICE_OPEN_COVER,
        {"entity_id": "cover.skip_update"},
        blocking=True,
    )

    # First STOPPED callback is skipped (the _skip_update=True path, line 121-123)
    device.operation_state = _STOPPED
    device.level = 1.0

    cb = _get_cover_callback(device, "cover.skip_update")
    cb()
    await hass.async_block_till_done()

    # Second STOPPED callback resets _skip_update (line 123 executed)
    cb()
    await hass.async_block_till_done()

    state = hass.states.get("cover.skip_update")
    assert state is not None
    assert state.state == STATE_OPEN
