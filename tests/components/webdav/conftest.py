"""Common fixtures for the WebDAV tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.webdav.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="webdav_client")
def mock_webdav_client() -> Generator[AsyncMock]:
    """Mock the aiowebdav client."""
    with (
        patch(
            "homeassistant.components.webdav.helpers.Client",
            autospec=True,
        ) as mock_webdav_client,
    ):
        mock = mock_webdav_client.return_value
        mock.check.return_value = True
        mock.mkdir.return_value = True
        yield mock
