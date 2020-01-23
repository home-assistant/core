"""Common tradfri test fixtures."""
from unittest.mock import patch

import pytest

from tests.common import mock_coro


@pytest.fixture
def mock_gateway_info():
    """Mock get_gateway_info."""
    with patch(
        "homeassistant.components.tradfri.config_flow.get_gateway_info"
    ) as mock_gateway:
        yield mock_gateway


@pytest.fixture
def mock_entry_setup():
    """Mock entry setup."""
    with patch("homeassistant.components.tradfri.async_setup_entry") as mock_setup:
        mock_setup.return_value = mock_coro(True)
        yield mock_setup
