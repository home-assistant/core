"""Test configuration for Shelly."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_coap():
    """Mock out coap."""
    with patch("homeassistant.components.shelly.get_coap_context"):
        yield
