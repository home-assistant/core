"""Define fixtures available for all tests."""
from unittest.mock import patch

import pytest

from . import _get_mock_client


@pytest.fixture
def cfupdate(hass):
    """Mock the CloudflareUpdater for easier testing."""
    mock_cfupdate = _get_mock_client()
    with patch(
        "homeassistant.components.cloudflare.pycfdns.Client",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api


@pytest.fixture
def cfupdate_flow(hass):
    """Mock the CloudflareUpdater for easier config flow testing."""
    mock_cfupdate = _get_mock_client()
    with patch(
        "homeassistant.components.cloudflare.pycfdns.Client",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api
