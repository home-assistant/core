"""Common tradfri test fixtures."""
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_gateway_info():
    """Mock get_gateway_info."""
    with patch('homeassistant.components.tradfri.config_flow.'
               'get_gateway_info') as mock_gateway:
        yield mock_gateway
