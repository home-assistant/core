"""The tests for the everlights component."""
from homeassistant.components.everlights import light as everlights


def test_color_rgb_to_int() -> None:
    """Test RGB to integer conversion."""
    assert everlights.color_rgb_to_int(0x00, 0x00, 0x00) == 0x000000
    assert everlights.color_rgb_to_int(0xFF, 0xFF, 0xFF) == 0xFFFFFF
    assert everlights.color_rgb_to_int(0x12, 0x34, 0x56) == 0x123456


def test_int_to_rgb() -> None:
    """Test integer to RGB conversion."""
    assert everlights.color_int_to_rgb(0x000000) == (0x00, 0x00, 0x00)
    assert everlights.color_int_to_rgb(0xFFFFFF) == (0xFF, 0xFF, 0xFF)
    assert everlights.color_int_to_rgb(0x123456) == (0x12, 0x34, 0x56)
