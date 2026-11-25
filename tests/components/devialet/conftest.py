"""Fixtures for the Devialet integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, PropertyMock, patch

from devialet import DevialetApi
import pytest


@pytest.fixture(autouse=True)
def mock_upnp_discovery() -> Generator[AsyncMock]:
    """Prevent UPnP discovery on the network."""
    with patch.object(
        DevialetApi, "async_discover_upnp_device", autospec=True
    ) as mock_discover:
        yield mock_discover


@pytest.fixture
def mock_upnp_available() -> Generator[None]:
    """Mock a discovered UPnP renderer."""
    with patch.object(
        DevialetApi, "upnp_available", new_callable=PropertyMock, return_value=True
    ):
        yield


@pytest.fixture
def mock_play_url_source() -> Generator[AsyncMock]:
    """Mock playing a URL over UPnP."""
    with patch.object(
        DevialetApi, "async_play_url_source", return_value=True
    ) as mock_play:
        yield mock_play
