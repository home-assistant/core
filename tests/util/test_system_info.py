"""Tests for the system info helper."""

from unittest.mock import patch

from homeassistant.util.system_info import is_official_image


async def test_is_official_image() -> None:
    """Test is_official_image."""
    is_official_image.cache_clear()
    with patch("homeassistant.util.system_info.os.path.isfile", return_value=True):
        assert is_official_image() is True
    is_official_image.cache_clear()
    with patch("homeassistant.util.system_info.os.path.isfile", return_value=False):
        assert is_official_image() is False
