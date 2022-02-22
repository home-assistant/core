"""Test the Hassio helper."""
from unittest.mock import patch

from homeassistant.helpers.supervisor import has_supervisor


async def test_has_supervisor_yes():
    """Test has_supervisor when supervisor available."""
    with patch("homeassistant.helpers.supervisor.os.environ", {"SUPERVISOR": True}):
        assert has_supervisor()


async def test_has_supervisor_no():
    """Test has_supervisor when supervisor not available."""
    with patch("homeassistant.helpers.supervisor.os.environ"):
        assert not has_supervisor()
