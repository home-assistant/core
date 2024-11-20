"""Tests for the YouTube integration."""

from collections.abc import AsyncGenerator
import json

from youtubeaio.models import YouTubeChannel, YouTubePlaylistItem, YouTubeSubscription
from youtubeaio.types import AuthScope

from tests.common import load_fixture


class MockYouTube:
    """Service which returns mock objects."""

    _thrown_error: Exception | None = None

    def __init__(
        self,
        channel_fixture: str = "youtube/get_channel.json",
        playlist_items_fixture: str = "youtube/get_playlist_items.json",
        subscriptions_fixture: str = "youtube/get_subscriptions.json",
    ) -> None:
        """Initialize mock service."""
        self._channel_fixture = channel_fixture
        self._playlist_items_fixture = playlist_items_fixture
        self._subscriptions_fixture = subscriptions_fixture

    async def set_user_authentication(
        self, token: str, scopes: list[AuthScope]
    ) -> None:
        """Authenticate the user."""

    async def get_user_channels(self) -> AsyncGenerator[YouTubeChannel]:
        """Get channels for authenticated user."""
        channels = json.loads(load_fixture(self._channel_fixture))
        for item in channels["items"]:
            yield YouTubeChannel(**item)

    async def get_channels(
        self, channel_ids: list[str]
    ) -> AsyncGenerator[YouTubeChannel]:
        """Get channels."""
        if self._thrown_error is not None:
            raise self._thrown_error
        channels = json.loads(load_fixture(self._channel_fixture))
        for item in channels["items"]:
            yield YouTubeChannel(**item)

    async def get_playlist_items(
        self, playlist_id: str, amount: int
    ) -> AsyncGenerator[YouTubePlaylistItem]:
        """Get channels."""
        channels = json.loads(load_fixture(self._playlist_items_fixture))
        for item in channels["items"]:
            yield YouTubePlaylistItem(**item)

    async def get_user_subscriptions(self) -> AsyncGenerator[YouTubeSubscription]:
        """Get channels for authenticated user."""
        channels = json.loads(load_fixture(self._subscriptions_fixture))
        for item in channels["items"]:
            yield YouTubeSubscription(**item)

    def set_thrown_exception(self, exception: Exception) -> None:
        """Set thrown exception for testing purposes."""
        self._thrown_error = exception
