"""Test the Hassio helper."""
from unittest.mock import patch

from homeassistant.helpers.hassio import is_hassio


async def test_is_hassio_yes():
    """Test is_hassio when supervisor available."""
    with patch("homeassistant.helpers.hassio.os.environ", {"HASSIO": True}):
        assert is_hassio()


async def test_is_hassio_no():
    """Test is_hassio when supervisor not available."""
    with patch("homeassistant.helpers.hassio.os.environ"):
        assert not is_hassio()
