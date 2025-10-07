"""Tests for ONVIF PTZ (Pan-Tilt-Zoom) functionality.

These tests validate that ONVIFDevice.async_perform_ptz correctly builds requests,
validates required parameters, respects PTZ capability flags, and handles errors
gracefully across all supported PTZ move modes.
"""

import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

from onvif.exceptions import ONVIFError
import pytest

from homeassistant.components.onvif import ONVIFDevice
from homeassistant.components.onvif.const import (
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    ZOOM_IN,
    ZOOM_OUT,
    MoveMode,
    MoveModeRequirement,
)
from homeassistant.components.onvif.device import MissingMoveRequirementError
from homeassistant.components.onvif.models import PTZ as PTZCaps
from homeassistant.core import HomeAssistant

from . import setup_onvif_integration


def apply_ptz_capabilities(
    device, *, continuous=True, relative=True, absolute=True, presets=None
):
    """Helper to apply PTZ capability flags and presets to a test device."""
    caps = PTZCaps(
        continuous=continuous, relative=relative, absolute=absolute, presets=presets
    )
    device.profiles[0].ptz = caps
    return caps


@pytest.fixture
async def ptz_device_and_camera(hass: HomeAssistant):
    """Fixture that sets up ONVIF device and camera with patched PTZ methods."""
    _, camera, device = await setup_onvif_integration(hass)
    device.async_perform_ptz = ONVIFDevice.async_perform_ptz.__get__(
        device, ONVIFDevice
    )
    device._apply_dir = ONVIFDevice._apply_dir
    device._supports_move_mode = ONVIFDevice._supports_move_mode
    device._check_move_mode_required_params = (
        ONVIFDevice._check_move_mode_required_params
    )

    return device, camera


@pytest.fixture
def mock_ptz_service(ptz_device_and_camera: tuple[MagicMock, MagicMock]):
    """Fixture that creates and injects a mocked PTZ service into the camera."""
    _, camera = ptz_device_and_camera
    ptz_service = MagicMock()
    ptz_service.create_type = MagicMock(side_effect=lambda t: types.SimpleNamespace())
    ptz_service.ContinuousMove = AsyncMock()
    ptz_service.RelativeMove = AsyncMock()
    ptz_service.AbsoluteMove = AsyncMock()
    ptz_service.GotoPreset = AsyncMock()
    ptz_service.Stop = AsyncMock()

    camera.create_ptz_service = AsyncMock(return_value=ptz_service)
    return ptz_service


@pytest.fixture(autouse=True)
def patch_no_asyncio_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture that patches asyncio.sleep to avoid delays in tests."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_continuous_move_builds_velocity_and_stops(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test ContinuousMove builds velocity and issues a Stop command."""
    device, camera = ptz_device_and_camera
    ptz_service = mock_ptz_service
    apply_ptz_capabilities(device, continuous=True, relative=True, absolute=True)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
        speed=0.5,
        continuous_duration=0.1,
        pan=DIR_RIGHT,
        tilt=None,
        zoom=ZOOM_IN,
    )

    camera.create_ptz_service.assert_awaited_once()

    ptz_service.ContinuousMove.assert_awaited_once()
    req = ptz_service.ContinuousMove.await_args.args[0]
    assert req.ProfileToken == device.profiles[0].token
    vel = req.Velocity
    assert vel["PanTilt"]["x"] != 0.0 and vel["PanTilt"]["y"] == 0.0
    assert vel["Zoom"]["x"] != 0.0

    ptz_service.Stop.assert_awaited_once()
    stop_req = ptz_service.Stop.await_args.args[0]
    assert stop_req.PanTilt is True and stop_req.Zoom is True
    assert stop_req.ProfileToken == device.profiles[0].token


@pytest.mark.asyncio
async def test_continuous_move_only_tilt_builds_y_axis(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test ContinuousMove when only tilt is provided builds y-axis velocity."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, continuous=True, relative=False, absolute=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
        speed=0.4,
        continuous_duration=0.05,
        tilt=DIR_UP,
    )
    req = mock_ptz_service.ContinuousMove.await_args.args[0]
    vel = req.Velocity
    assert "PanTilt" in vel and "Zoom" not in vel
    assert vel["PanTilt"]["x"] == 0.0 and vel["PanTilt"]["y"] == 0.4


@pytest.mark.asyncio
async def test_relative_move_pan_only(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test RelativeMove builds PanTilt translation when only pan is given."""
    device, _ = ptz_device_and_camera

    apply_ptz_capabilities(device, relative=True, continuous=False, absolute=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        distance=0.2,
        speed=0.7,
        pan=DIR_LEFT,
        tilt=None,
        zoom=None,
    )

    req = mock_ptz_service.RelativeMove.await_args.args[0]
    trans = req.Translation
    assert "PanTilt" in trans and "Zoom" not in trans
    assert trans["PanTilt"]["x"] == -0.2 and trans["PanTilt"]["y"] == 0.0
    assert req.Speed["PanTilt"]["x"] == 0.7 and req.Speed["PanTilt"]["y"] == 0.7


@pytest.mark.asyncio
async def test_relative_move_zoom_only(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test RelativeMove builds Zoom translation when only zoom is given."""
    device, _ = ptz_device_and_camera

    apply_ptz_capabilities(device, relative=True, continuous=False, absolute=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        distance=0.1,
        speed=0.5,
        zoom=ZOOM_OUT,
    )

    req = mock_ptz_service.RelativeMove.await_args.args[0]
    trans = req.Translation
    assert "Zoom" in trans and "PanTilt" not in trans
    assert trans["Zoom"]["x"] == -0.1
    assert "Zoom" in req.Speed and "PanTilt" not in req.Speed
    assert req.Speed["Zoom"]["x"] == 0.5


@pytest.mark.asyncio
async def test_relative_move_speed_only_for_present_axes(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test RelativeMove applies speed only to present axes."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, relative=True, continuous=False, absolute=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        distance=0.25,
        speed=0.9,
        pan=DIR_RIGHT,
        tilt=None,
        zoom=None,
    )
    req = mock_ptz_service.RelativeMove.await_args.args[0]
    assert "PanTilt" in req.Speed and "Zoom" not in req.Speed
    assert req.Speed["PanTilt"]["x"] == 0.9 and req.Speed["PanTilt"]["y"] == 0.9
    trans = req.Translation
    assert trans["PanTilt"]["x"] == 0.25 and trans["PanTilt"]["y"] == 0.0


@pytest.mark.asyncio
async def test_requirements_missing_distance_on_relative_blocks(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test RelativeMove blocks call if distance is missing."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, relative=True, continuous=False, absolute=False)
    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        pan=DIR_LEFT,
    )
    mock_ptz_service.RelativeMove.assert_not_called()


@pytest.mark.asyncio
async def test_absolute_move_uses_position(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test AbsoluteMove builds Position and Speed for PanTilt axes."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, absolute=True, relative=False, continuous=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.ABSOLUTE,
        distance=0.3,
        speed=0.8,
        pan=DIR_RIGHT,
        tilt=DIR_DOWN,
    )

    req = mock_ptz_service.AbsoluteMove.await_args.args[0]
    assert hasattr(req, "Position")
    pos = req.Position
    assert "PanTilt" in pos and "Zoom" not in pos
    assert set(pos["PanTilt"].keys()) == {"x", "y"}
    assert req.Position["PanTilt"]["x"] == 0.3 and req.Position["PanTilt"]["y"] == -0.3
    assert req.Speed["PanTilt"]["x"] == 0.8 and req.Speed["PanTilt"]["y"] == 0.8


@pytest.mark.asyncio
async def test_absolute_move_zoom_only_builds_zoom_node(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test AbsoluteMove builds Position and Speed for Zoom only."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, absolute=True, relative=False, continuous=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.ABSOLUTE,
        distance=0.6,
        speed=0.2,
        zoom=ZOOM_IN,
    )
    req = mock_ptz_service.AbsoluteMove.await_args.args[0]
    assert "Zoom" in req.Position and "PanTilt" not in req.Position
    assert req.Position["Zoom"]["x"] == 0.6
    assert "Zoom" in req.Speed and "PanTilt" not in req.Speed
    assert req.Speed["Zoom"]["x"] == 0.2


@pytest.mark.asyncio
async def test_requirements_missing_axes_on_absolute_blocks(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test AbsoluteMove blocks call if axes are missing."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, absolute=True, relative=False, continuous=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.ABSOLUTE,
        distance=0.3,
        speed=0.1,
    )
    mock_ptz_service.AbsoluteMove.assert_not_called()


@pytest.mark.asyncio
async def test_goto_preset_validates(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test GotoPreset validates preset existence before issuing call."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(
        device, presets=["1", "2"], continuous=False, relative=False, absolute=False
    )

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.GOTOPRESET,
        preset="42",
        speed=0.4,
    )
    mock_ptz_service.GotoPreset.assert_not_awaited()

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.GOTOPRESET,
        preset="2",
        speed=0.4,
    )
    mock_ptz_service.GotoPreset.assert_awaited_once()
    req = mock_ptz_service.GotoPreset.await_args.args[0]
    assert req.PresetToken == "2"
    assert req.Speed["PanTilt"]["x"] == 0.4 and req.Speed["Zoom"]["x"] == 0.4


@pytest.mark.asyncio
async def test_requirements_missing_preset_on_goto_blocks(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test GotoPreset blocks call if no preset is provided."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(
        device, presets=["1", "2"], continuous=False, relative=False, absolute=False
    )

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.GOTOPRESET,
        speed=0.3,
    )
    mock_ptz_service.GotoPreset.assert_not_called()


@pytest.mark.asyncio
async def test_stop_move_sets_flags_and_calls_stop(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test StopMove sets flags and calls Stop request."""
    device, _ = ptz_device_and_camera

    apply_ptz_capabilities(device, continuous=False, relative=False, absolute=False)

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.STOP,
    )

    mock_ptz_service.Stop.assert_awaited_once()
    stop_req = mock_ptz_service.Stop.await_args.args[0]
    assert stop_req.ProfileToken == device.profiles[0].token
    assert stop_req.PanTilt is True and stop_req.Zoom is True


@pytest.mark.asyncio
async def test_ptz_capability_disabled_skips_everything(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test PTZ disabled capability skips all move calls."""
    device, _ = ptz_device_and_camera
    device.capabilities.ptz = False

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        distance=0.1,
        pan=DIR_RIGHT,
    )

    assert not mock_ptz_service.ContinuousMove.called
    assert not mock_ptz_service.RelativeMove.called
    assert not mock_ptz_service.AbsoluteMove.called
    assert not mock_ptz_service.GotoPreset.called
    assert not mock_ptz_service.Stop.called


@pytest.mark.asyncio
async def test_move_mode_requirement_validation_blocks_calls(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test validation blocks PTZ calls when required parameters are missing."""
    device, _ = ptz_device_and_camera

    apply_ptz_capabilities(device, relative=True, continuous=True, absolute=False)

    # RelativeMove no axes
    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        distance=0.1,
    )
    mock_ptz_service.RelativeMove.assert_not_awaited()

    # ContinuousMove no speed
    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
        continuous_duration=0.1,
        pan=DIR_RIGHT,
    )
    mock_ptz_service.ContinuousMove.assert_not_awaited()

    # ContinuousMove no continuous_duration
    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
        speed=0.1,
        pan=DIR_RIGHT,
    )
    mock_ptz_service.ContinuousMove.assert_not_awaited()

    # ContinuousMove no requirements
    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
    )
    mock_ptz_service.ContinuousMove.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_mode_skips(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test unsupported PTZ move modes are skipped without errors."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(
        device, continuous=False, relative=False, absolute=False, presets=None
    )

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
        speed=0.5,
        continuous_duration=0.1,
        pan=DIR_RIGHT,
    )
    mock_ptz_service.ContinuousMove.assert_not_called()

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.RELATIVE,
        distance=0.1,
        pan=DIR_RIGHT,
    )
    mock_ptz_service.RelativeMove.assert_not_called()

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.ABSOLUTE,
        distance=0.3,
        pan=DIR_RIGHT,
    )
    mock_ptz_service.AbsoluteMove.assert_not_called()

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.GOTOPRESET,
        preset="1",
        speed=0.4,
    )
    mock_ptz_service.GotoPreset.assert_not_called()


@pytest.mark.asyncio
async def test_onvif_error_is_caught_and_does_not_raise(
    ptz_device_and_camera: tuple[MagicMock, MagicMock], mock_ptz_service: MagicMock
) -> None:
    """Test ONVIFError is caught and does not propagate."""
    device, _ = ptz_device_and_camera
    apply_ptz_capabilities(device, continuous=True, relative=False, absolute=False)

    err = ONVIFError("boom")
    setattr(err, "reason", "Something else")
    mock_ptz_service.ContinuousMove.side_effect = err

    await device.async_perform_ptz(
        profile=device.profiles[0],
        move_mode=MoveMode.CONTINUOUS,
        speed=0.4,
        continuous_duration=0.05,
        pan=DIR_RIGHT,
    )

    mock_ptz_service.ContinuousMove.assert_awaited_once()
    mock_ptz_service.Stop.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("move_mode", "kwargs", "expected_missing"),
    [
        # CONTINUOUS
        (
            MoveMode.CONTINUOUS,
            {
                "pan": None,
                "tilt": None,
                "zoom": None,
                "speed": 0.2,
                "continuous_duration": 0.1,
                "distance": None,
                "preset": None,
            },
            {MoveModeRequirement.AXES},
        ),
        (
            MoveMode.CONTINUOUS,
            {
                "pan": "RIGHT",
                "tilt": None,
                "zoom": None,
                "speed": None,
                "continuous_duration": 0.1,
                "distance": None,
                "preset": None,
            },
            {MoveModeRequirement.SPEED},
        ),
        (
            MoveMode.CONTINUOUS,
            {
                "pan": "RIGHT",
                "tilt": None,
                "zoom": None,
                "speed": 0.2,
                "continuous_duration": None,
                "distance": None,
                "preset": None,
            },
            {MoveModeRequirement.CONTINUOUS_DURATION},
        ),
        # RELATIVE
        (
            MoveMode.RELATIVE,
            {
                "pan": None,
                "tilt": None,
                "zoom": None,
                "speed": None,
                "continuous_duration": None,
                "distance": 0.1,
                "preset": None,
            },
            {MoveModeRequirement.AXES},
        ),
        (
            MoveMode.RELATIVE,
            {
                "pan": "RIGHT",
                "tilt": None,
                "zoom": None,
                "speed": None,
                "continuous_duration": None,
                "distance": None,
                "preset": None,
            },
            {MoveModeRequirement.DISTANCE},
        ),
        # ABSOLUTE
        (
            MoveMode.ABSOLUTE,
            {
                "pan": None,
                "tilt": None,
                "zoom": None,
                "speed": None,
                "continuous_duration": None,
                "distance": 0.5,
                "preset": None,
            },
            {MoveModeRequirement.AXES},
        ),
        # GOTOPRESET
        (
            MoveMode.GOTOPRESET,
            {
                "pan": None,
                "tilt": None,
                "zoom": None,
                "speed": None,
                "continuous_duration": None,
                "distance": None,
                "preset": None,
            },
            {MoveModeRequirement.PRESET},
        ),
    ],
)
async def test_validator_raises_with_correct_missing(
    ptz_device_and_camera, move_mode, kwargs, expected_missing
) -> None:
    """The validator must raise MissingMoveRequirementError with the correct missing requirements set."""
    device, _ = ptz_device_and_camera

    with pytest.raises(MissingMoveRequirementError) as excinfo:
        device._check_move_mode_required_params(move_mode, **kwargs)

    err = excinfo.value
    assert err.move_mode == move_mode
    assert expected_missing.issubset(err.missing)
    msg = str(err).lower()
    for req in expected_missing:
        key = req.name.lower()
        assert key in msg or "pan/tilt/zoom" in msg
