"""Define fixtures available for all tests."""
from pytest import fixture

from . import _get_mock_cfupdate

from tests.async_mock import patch


@fixture
def cfupdate(hass):
    """Mock the CloudflareUpdater for easier testing."""
    mock_cfupdate = _get_mock_cfupdate()
    with patch(
        "homeassistant.components.cloudflare.CloudflareUpdater",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api


@fixture
def cfupdate_flow(hass):
    """Mock the CloudflareUpdater for easier config flow testing."""
    mock_cfupdate = _get_mock_cfupdate()
    with patch(
        "homeassistant.components.cloudflare.config_flow.CloudflareUpdater",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api
