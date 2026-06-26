"""Tests for the Amcrest switch platform."""

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest import AmcrestDevice
from homeassistant.components.amcrest.switch import SWITCH_TYPES, AmcrestSwitch

from .conftest import CAMERA_NAME, SERIAL_NUMBER, _MockAmcrestAPI

_PRIVACY_MODE = SWITCH_TYPES[0]


def _make_switch(device: AmcrestDevice) -> AmcrestSwitch:
    return AmcrestSwitch(CAMERA_NAME, device, _PRIVACY_MODE)


def test_switch_unique_id(device: AmcrestDevice) -> None:
    """Unique ID combines serial number, switch key, and channel."""
    switch = _make_switch(device)
    assert switch._attr_unique_id == f"{SERIAL_NUMBER}-{_PRIVACY_MODE.key}-0"


def test_switch_no_unique_id_without_serial(mock_api: _MockAmcrestAPI) -> None:
    """No unique_id is assigned when the device has no serial number."""
    device = AmcrestDevice(
        api=mock_api,
        authentication=None,
        ffmpeg_arguments=["-pred", "1"],
        stream_source="snapshot",
        resolution=0,
        control_light=True,
        serial_number=None,
    )
    switch = _make_switch(device)
    assert switch._attr_unique_id is None


@pytest.mark.parametrize(
    ("privacy_mode", "expected_is_on"),
    [
        pytest.param(True, True, id="privacy_on"),
        pytest.param(False, False, id="privacy_off"),
    ],
)
async def test_switch_update(
    mock_api: _MockAmcrestAPI,
    device: AmcrestDevice,
    privacy_mode: bool,
    expected_is_on: bool,
) -> None:
    """async_update reflects the current privacy mode state."""
    mock_api.privacy_mode = privacy_mode
    switch = _make_switch(device)
    await switch.async_update()
    assert switch.is_on is expected_is_on


async def test_switch_update_skips_when_unavailable(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """async_update makes no API call when the camera is unavailable."""
    mock_api.available = False
    switch = _make_switch(device)
    initial_state = switch._attr_is_on
    await switch.async_update()
    assert switch._attr_is_on is initial_state  # state unchanged


async def test_switch_update_handles_error(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """AmcrestError during update is caught and does not propagate."""
    mock_api.set_error("privacy_config", AmcrestError("timeout"))
    switch = _make_switch(device)
    await switch.async_update()  # must not raise
