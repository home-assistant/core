"""Tests for the Amcrest switch platform."""

import logging

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest import AmcrestDevice
from homeassistant.components.amcrest.switch import SWITCH_TYPES, AmcrestSwitch

from .conftest import CAMERA_NAME, _MockAmcrestAPI

_PRIVACY_MODE = SWITCH_TYPES[0]


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
    """async_update reflects the privacy mode reported by the camera."""
    mock_api.privacy_mode = privacy_mode
    switch = AmcrestSwitch(CAMERA_NAME, device, _PRIVACY_MODE)

    await switch.async_update()

    assert switch.is_on is expected_is_on


async def test_switch_update_skips_when_unavailable(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """async_update does not query the camera while it is unavailable."""
    mock_api.privacy_mode = True
    mock_api.available = False
    switch = AmcrestSwitch(CAMERA_NAME, device, _PRIVACY_MODE)

    await switch.async_update()

    # is_on stays None instead of picking up privacy_mode=True, which is only
    # reachable by querying the camera.
    assert switch.is_on is None


async def test_switch_update_handles_error(
    mock_api: _MockAmcrestAPI,
    device: AmcrestDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An AmcrestError during update is logged and leaves the last state intact."""
    mock_api.privacy_mode = True
    switch = AmcrestSwitch(CAMERA_NAME, device, _PRIVACY_MODE)
    await switch.async_update()
    assert switch.is_on is True

    mock_api.set_error("privacy_config", AmcrestError("timeout"))
    with caplog.at_level(logging.ERROR):
        await switch.async_update()

    assert switch.is_on is True
    assert (
        f"Could not update {CAMERA_NAME} Privacy Mode switch due to error: AmcrestError"
        in caplog.text
    )
