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

    def list(
        self,
        part: str,
        id: str | None = None,
        mine: bool | None = None,
        maxResults: int | None = None,
    ) -> MockRequest:
        """Return a fixture."""
        return MockRequest(fixture="youtube/get_channel.json")


class MockPlaylistItems:
    """Mock object for playlist items."""

    def list(
        self,
        part: str,
        playlistId: str,
        maxResults: int | None = None,
    ) -> MockRequest:
        """Return a fixture."""
        return MockRequest(fixture="youtube/get_playlist_items.json")


class MockSubscriptions:
    """Mock object for subscriptions."""

    def list(self, part: str, mine: bool, maxResults: int | None = None) -> MockRequest:
        """Return a fixture."""
        return MockRequest(fixture="youtube/get_subscriptions.json")


class MockService:
    """Service which returns mock objects."""

    def channels(self) -> MockChannels:
        """Return a mock object."""
        return MockChannels()

    def playlistItems(self) -> MockPlaylistItems:
        """Return a mock object."""
        return MockPlaylistItems()

    def subscriptions(self) -> MockSubscriptions:
        """Return a mock object."""
        return MockSubscriptions()
