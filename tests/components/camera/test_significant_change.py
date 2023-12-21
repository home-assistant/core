"""Test the Camera significant change platform."""
from homeassistant.components.camera import STATE_IDLE, STATE_RECORDING
from homeassistant.components.camera.significant_change import (
    async_check_significant_change,
)


async def test_significant_change() -> None:
    """Detect Camera significant changes."""
    attrs = {}
    assert not async_check_significant_change(
        None, STATE_IDLE, attrs, STATE_IDLE, attrs
    )
    assert not async_check_significant_change(
        None, STATE_IDLE, attrs, STATE_IDLE, {"dummy": "dummy"}
    )
    assert async_check_significant_change(
        None, STATE_IDLE, attrs, STATE_RECORDING, attrs
    )
