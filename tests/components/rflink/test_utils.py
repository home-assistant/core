"""Test for RFLink utils methods."""

from homeassistant.components.rflink.utils import (
    brightness_to_rflink,
    rflink_to_brightness,
)


async def test_utils() -> None:
    """Test all utils methods."""
    # test brightness_to_rflink
    assert brightness_to_rflink(0) == 0
    assert brightness_to_rflink(17) == 1
    assert brightness_to_rflink(34) == 2
    assert brightness_to_rflink(85) == 5
    assert brightness_to_rflink(170) == 10
    assert brightness_to_rflink(255) == 15

    assert brightness_to_rflink(10) == 0
    assert brightness_to_rflink(20) == 1
    assert brightness_to_rflink(30) == 1
    assert brightness_to_rflink(40) == 2
    assert brightness_to_rflink(50) == 2
    assert brightness_to_rflink(60) == 3
    assert brightness_to_rflink(70) == 4
    assert brightness_to_rflink(80) == 4

    # test rflink_to_brightness
    assert rflink_to_brightness(0) == 0
    assert rflink_to_brightness(1) == 17
    assert rflink_to_brightness(5) == 85
    assert rflink_to_brightness(10) == 170
    assert rflink_to_brightness(12) == 204
    assert rflink_to_brightness(15) == 255
