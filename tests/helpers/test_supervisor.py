"""Test the Hassio helper."""
from unittest.mock import patch

from homeassistant.helpers.supervisor import is_supervised


async def test_is_supervised_yes():
    """Test is_supervised when supervisor available."""
    with patch("homeassistant.helpers.supervisor.os.environ", {"SUPERVISOR": True}):
        assert is_supervised()


async def test_is_supervised_no():
    """Test is_supervised when supervisor not available."""
    with patch("homeassistant.helpers.supervisor.os.environ"):
        assert not is_supervised()
