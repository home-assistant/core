"""Tests for the YouTube integration."""
from dataclasses import dataclass
import json
from typing import Any

from tests.common import load_fixture


@dataclass
class MockRequest:
    """Mock object for a request."""

    fixture: str

    def execute(self) -> dict[str, Any]:
        """Return a fixture."""
        return json.loads(load_fixture(self.fixture))


class MockChannels:
    """Mock object for channels."""

    def __init__(self, fixture: str):
        """Initialize mock channels."""
        self._fixture = fixture

    def list(
        self,
        part: str,
        id: str | None = None,
        mine: bool | None = None,
        maxResults: int | None = None,
    ) -> MockRequest:
        """Return a fixture."""
        return MockRequest(fixture=self._fixture)


class MockPlaylistItems:
    """Mock object for playlist items."""

    def __init__(self, fixture: str):
        """Initialize mock playlist items."""
        self._fixture = fixture

    def list(
        self,
        part: str,
        playlistId: str,
        maxResults: int | None = None,
    ) -> MockRequest:
        """Return a fixture."""
        return MockRequest(fixture=self._fixture)


class MockSubscriptions:
    """Mock object for subscriptions."""

    def __init__(self, fixture: str):
        """Initialize mock subscriptions."""
        self._fixture = fixture

    def list(
        self,
        part: str,
        mine: bool,
        maxResults: int | None = None,
        pageToken: str | None = None,
    ) -> MockRequest:
        """Return a fixture."""
        return MockRequest(fixture=self._fixture)


class MockService:
    """Service which returns mock objects."""

    def __init__(
        self,
        channel_fixture: str = "youtube/get_channel.json",
        playlist_items_fixture: str = "youtube/get_playlist_items.json",
        subscriptions_fixture: str = "youtube/get_subscriptions.json",
    ):
        """Initialize mock service."""
        self._channel_fixture = channel_fixture
        self._playlist_items_fixture = playlist_items_fixture
        self._subscriptions_fixture = subscriptions_fixture

    def channels(self) -> MockChannels:
        """Return a mock object."""
        return MockChannels(self._channel_fixture)

    def playlistItems(self) -> MockPlaylistItems:
        """Return a mock object."""
        return MockPlaylistItems(self._playlist_items_fixture)

    def subscriptions(self) -> MockSubscriptions:
        """Return a mock object."""
        return MockSubscriptions(self._subscriptions_fixture)
