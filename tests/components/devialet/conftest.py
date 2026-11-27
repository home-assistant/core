"""Fixtures for the Devialet integration tests."""

import asyncio
from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, PropertyMock, patch

from devialet import DevialetApi
import pytest


@pytest.fixture(autouse=True)
def mock_listen() -> Generator[AsyncMock]:
    """Mock the push notification connection, the callbacks are in the call args."""

    async def listen(
        self: DevialetApi,
        on_update: Callable[[], None],
        on_connection_change: Callable[[bool], None],
    ) -> None:
        await asyncio.Event().wait()

    with patch.object(
        DevialetApi, "async_listen", autospec=True, side_effect=listen
    ) as mock:
        yield mock


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
