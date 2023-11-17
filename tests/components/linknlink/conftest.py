"""LinknLink test helpers."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_heartbeat():
    """Mock linknlink heartbeat."""
    with patch("homeassistant.components.linknlink.heartbeat.llk.ping"):
        yield
