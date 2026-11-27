"""Test the Matter utilities."""

from homeassistant.components.matter.util import get_clean_name


def test_get_clean_name() -> None:
    """Test get_clean_name helper.

    Test device names that are assigned to `null`
    or have a trailing null char with spaces.
    """
    assert get_clean_name(None) is None
    assert get_clean_name("\x00") is None
    assert get_clean_name("   \x00") is None
    assert get_clean_name("") is None
    assert get_clean_name("Mock device") == "Mock device"
    assert get_clean_name("Mock device                    \x00") == "Mock device"
