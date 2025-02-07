"""Test the Camera significant change platform."""

from homeassistant.components.camera import CameraState
from homeassistant.components.camera.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Camera significant changes."""
    attrs = {}
    assert not async_check_significant_change(
        None, CameraState.IDLE, attrs, CameraState.IDLE, attrs
    )
    assert not async_check_significant_change(
        None, CameraState.IDLE, attrs, CameraState.IDLE, {"dummy": "dummy"}
    )
    assert async_check_significant_change(
        None, CameraState.IDLE, attrs, CameraState.RECORDING, attrs
    )
