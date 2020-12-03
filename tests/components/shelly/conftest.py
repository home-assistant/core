"""Test configuration for Shelly."""
import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def mock_coap():
    """Mock out coap."""
    with patch("homeassistant.components.shelly.get_coap_context"):
        yield
