import pytest

from tests.async_mock import patch


@pytest.fixture
def mock_update():
    """Pytest fixture for tcp sensor update."""
    with patch("homeassistant.components.tcp.sensor.TcpSensor.update") as mock_update:
        yield mock_update.return_value
