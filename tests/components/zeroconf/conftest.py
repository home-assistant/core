"""conftest for zeroconf."""
import pytest

from tests.async_mock import patch


@pytest.fixture
def mock_zeroconf():
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc:
        yield mock_zc.return_value
