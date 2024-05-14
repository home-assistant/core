"""Fixtures for testing qBittorrent component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
import requests_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock qbittorrent entry setup."""
    with patch(
        "homeassistant.components.qbittorrent.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_api() -> Generator[requests_mock.Mocker, None, None]:
    """Mock the qbittorrent API."""
    with requests_mock.Mocker() as mocker:
        mocker.get("http://localhost:8080/api/v2/app/preferences", status_code=403)
        mocker.get("http://localhost:8080/api/v2/transfer/speedLimitsMode")
        mocker.post("http://localhost:8080/api/v2/auth/login", text="Ok.")
        yield mocker
