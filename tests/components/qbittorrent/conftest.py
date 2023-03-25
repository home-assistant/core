"""Fixtures for testing qBittorrent component."""
from unittest.mock import patch

import pytest
from requests.exceptions import RequestException
from requests.sessions import Session


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock qbittorrent entry setup."""
    with patch(
        "homeassistant.components.qbittorrent.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock the qbittorrent API."""
    with patch.object(Session, "get"), patch.object(Session, "post"):
        yield


@pytest.fixture(name="ok")
def mock_api_login_ok():
    """Mock successful login."""

    class OkResponse:
        """Mock an OK response for login."""

        text: str = "Ok."

    with patch.object(Session, "post", return_value=OkResponse()):
        yield


@pytest.fixture(name="invalid_auth")
def mock_api_invalid_auth():
    """Mock invalid credential."""

    class InvalidAuthResponse:
        """Mock an invalid auth response."""

        text: str = "Wrong username/password"

    with patch.object(Session, "post", return_value=InvalidAuthResponse()):
        yield


@pytest.fixture(name="cannot_connect")
def mock_api_cannot_connect():
    """Mock connection failure."""
    with patch.object(Session, "get", side_effect=RequestException()):
        yield
