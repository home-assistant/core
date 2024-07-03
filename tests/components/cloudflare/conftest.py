"""Define fixtures available for all tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from . import get_mock_client


@pytest.fixture
def cfupdate() -> Generator[MagicMock]:
    """Mock the CloudflareUpdater for easier testing."""
    mock_cfupdate = get_mock_client()
    with patch(
        "homeassistant.components.cloudflare.pycfdns.Client",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api


@pytest.fixture
def cfupdate_flow() -> Generator[MagicMock]:
    """Mock the CloudflareUpdater for easier config flow testing."""
    mock_cfupdate = get_mock_client()
    with patch(
        "homeassistant.components.cloudflare.config_flow.pycfdns.Client",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api
