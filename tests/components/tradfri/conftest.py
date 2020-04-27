"""Common tradfri test fixtures."""
from asynctest import patch
import pytest


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
        mock_setup.return_value = True
        yield mock_setup
