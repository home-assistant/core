"""Conftest for speedtestdotnet."""

from unittest.mock import patch

import pytest

from . import MOCK_SERVERS


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.speedtestdotnet.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_api():
    """Mock entry setup."""
    with patch("speedtest.Speedtest") as mock_api:
        mock_api.return_value.get_servers.return_value = MOCK_SERVERS
        yield mock_api
