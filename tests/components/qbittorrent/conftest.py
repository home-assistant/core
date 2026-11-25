"""Fixtures for testing qBittorrent component."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
import requests_mock

from homeassistant.components.qbittorrent import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock qbittorrent entry setup."""
    with patch(
        "homeassistant.components.qbittorrent.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_api() -> Generator[requests_mock.Mocker]:
    """Mock the qbittorrent API."""
    with requests_mock.Mocker() as mocker:
        mocker.get("http://localhost:8080/api/v2/app/preferences", status_code=403)
        mocker.get("http://localhost:8080/api/v2/transfer/speedLimitsMode")
        mocker.post("http://localhost:8080/api/v2/auth/login", text="Ok.")
        yield mocker


@pytest.fixture
def sync_maindata() -> dict[str, Any]:
    """Return the sync main data the qbittorrent client returns."""
    return load_json_object_fixture("sync_maindata.json", DOMAIN)


@pytest.fixture
def mock_qbittorrent(sync_maindata: dict[str, Any]) -> Generator[AsyncMock]:
    """Mock qbittorrent client."""
    with patch(
        "homeassistant.components.qbittorrent.helpers.Client", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.sync_maindata.return_value = sync_maindata
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for qbittorrent."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://localhost:8080",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "adminadmin",
            CONF_VERIFY_SSL: False,
        },
        entry_id="01K6E7464PTQKDE24VAJQZPTH2",
    )
