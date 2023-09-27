"""Tests for the Twitch component."""
import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from twitchAPI.object.api import FollowedChannelsResult, TwitchUser
from twitchAPI.twitch import (
    InvalidTokenException,
    MissingScopeException,
    TwitchAPIException,
    TwitchAuthorizationException,
    TwitchResourceNotFound,
)
from twitchAPI.type import AuthScope, AuthType

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)


def _get_twitch_user(user_id: str = "123") -> TwitchUser:
    return TwitchUser(
        id=user_id,
        display_name="channel123",
        offline_image_url="logo.png",
        profile_image_url="logo.png",
        view_count=42,
    )


async def async_iterator(iterable) -> AsyncIterator:
    """Return async iterator."""
    for i in iterable:
        yield i


@dataclass
class UserSubscriptionMock:
    """User subscription mock."""

    broadcaster_id: str
    is_gift: bool


@dataclass
class FollowedChannelMock:
    """Followed channel mock."""

    broadcaster_login: str
    followed_at: str


@dataclass
class ChannelFollowerMock:
    """Channel follower mock."""

    user_id: str


@dataclass
class StreamMock:
    """Stream mock."""

    game_name: str
    title: str
    thumbnail_url: str


class TwitchUserFollowResultMock:
    """Mock for twitch user follow result."""

    def __init__(self, follows: list[FollowedChannelMock]) -> None:
        """Initialize mock."""
        self.total = len(follows)
        self.data = follows

    def __aiter__(self):
        """Return async iterator."""
        return async_iterator(self.data)


class ChannelFollowersResultMock:
    """Mock for twitch channel follow result."""

    def __init__(self, follows: list[dict[str, Any]]) -> None:
        """Initialize mock."""
        self.total = len(follows)
        self.data = follows

    def __aiter__(self):
        """Return async iterator."""
        return async_iterator(self.data)


STREAMS = StreamMock(
    game_name="Good game", title="Title", thumbnail_url="stream-medium.png"
)


class TwitchMock:
    """Mock for the twitch object."""

    _is_streaming = True
    _is_gifted = False
    _is_subscribed = False
    _is_following = True
    _different_user_id = False

    def __await__(self):
        """Add async capabilities to the mock."""
        t = asyncio.create_task(self._noop())
        yield from t
        return self

    def is_streaming(self, state: bool) -> None:
        """Set if the channel is streaming."""
        self._is_streaming = state

    def is_following(self, state: bool) -> None:
        """Set if the channel is followed."""
        self._is_following = state

    def is_subscribed(self, state: bool) -> None:
        """Set if the channel is subscribed."""
        self._is_subscribed = state

    def different_user_id(self, state: bool) -> None:
        """Set if the user id should be different."""
        self._different_user_id = state

    async def _noop(self):
        """Fake function to create task."""
        pass

    async def get_users(
        self, user_ids: list[str] | None = None, logins: list[str] | None = None
    ) -> AsyncGenerator[TwitchUser, None]:
        """Get list of mock users."""
        users = [_get_twitch_user("234" if self._different_user_id else "123")]
        for user in users:
            yield user

    def has_required_auth(
        self, required_type: AuthType, required_scope: list[AuthScope]
    ) -> bool:
        """Return if auth required."""
        return True

    async def check_user_subscription(
        self, broadcaster_id: str, user_id: str
    ) -> UserSubscriptionMock:
        """Check if the user is subscribed."""
        if self._is_subscribed:
            return UserSubscriptionMock(
                broadcaster_id=broadcaster_id, is_gift=self._is_gifted
            )
        raise TwitchResourceNotFound

    async def set_user_authentication(
        self,
        token: str,
        scope: list[AuthScope],
        validate: bool = True,
    ) -> None:
        """Set user authentication."""
        pass

    async def get_followed_channels(
        self, user_id: str, broadcaster_id: str | None = None
    ) -> FollowedChannelsResult:
        """Get followed channels."""
        if self._is_following:
            return TwitchUserFollowResultMock(
                [
                    FollowedChannelMock(
                        followed_at=datetime(year=2023, month=8, day=1),
                        broadcaster_login="internetofthings",
                    ),
                    FollowedChannelMock(
                        followed_at=datetime(year=2023, month=8, day=1),
                        broadcaster_login="homeassistant",
                    ),
                ]
            )
        return TwitchUserFollowResultMock([])

    async def get_channel_followers(
        self, broadcaster_id: str
    ) -> ChannelFollowersResultMock:
        """Get channel followers."""
        return ChannelFollowersResultMock([ChannelFollowerMock(user_id="abc")])

    async def get_streams(
        self, user_id: list[str], first: int
    ) -> AsyncGenerator[StreamMock, None]:
        """Get streams for the user."""
        streams = []
        if self._is_streaming:
            streams = [STREAMS]
        for stream in streams:
            yield stream


class TwitchUnauthorizedMock(TwitchMock):
    """Twitch mock to test if the client is unauthorized."""

    def __await__(self):
        """Add async capabilities to the mock."""
        raise TwitchAuthorizationException()


class TwitchMissingScopeMock(TwitchMock):
    """Twitch mock to test missing scopes."""

    async def set_user_authentication(
        self, token: str, scope: list[AuthScope], validate: bool = True
    ) -> None:
        """Set user authentication."""
        raise MissingScopeException()


class TwitchInvalidTokenMock(TwitchMock):
    """Twitch mock to test invalid token."""

    async def set_user_authentication(
        self, token: str, scope: list[AuthScope], validate: bool = True
    ) -> None:
        """Set user authentication."""
        raise InvalidTokenException()


class TwitchInvalidUserMock(TwitchMock):
    """Twitch mock to test invalid user."""

    async def get_users(
        self, user_ids: list[str] | None = None, logins: list[str] | None = None
    ) -> AsyncGenerator[TwitchUser, None]:
        """Get list of mock users."""
        if user_ids is not None or logins is not None:
            async for user in super().get_users(user_ids, logins):
                yield user
        else:
            for user in []:
                yield user


class TwitchAPIExceptionMock(TwitchMock):
    """Twitch mock to test when twitch api throws unknown exception."""

    async def check_user_subscription(
        self, broadcaster_id: str, user_id: str
    ) -> UserSubscriptionMock:
        """Check if the user is subscribed."""
        raise TwitchAPIException()
