"""Tests for Imou base entity helpers."""

from pyimouapi.ha_device import ImouHaDevice
import pytest

from homeassistant.components.imou.entity import imou_device_identifier


@pytest.mark.parametrize(
    ("set_channel", "expected_id"),
    [
        (False, "dev-1"),
        (True, "dev-1_ch9"),
    ],
)
def test_imou_device_identifier(
    set_channel: bool,
    expected_id: str,
) -> None:
    """Test registry identifier uses channel when present."""
    device = ImouHaDevice("dev-1", "Cam", "Imou", "model-x", "2.0")
    if set_channel:
        device.set_channel_id("ch9")
    assert imou_device_identifier(device) == expected_id
