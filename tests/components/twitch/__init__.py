"""Tests for the Twitch component."""
import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from twitchAPI.object import TwitchUser
from twitchAPI.twitch import (
    InvalidTokenException,
    MissingScopeException,
    TwitchAPIException,
    TwitchAuthorizationException,
    TwitchResourceNotFound,
)
from twitchAPI.types import AuthScope, AuthType

USER_OBJECT: TwitchUser = TwitchUser(
    id=123,
    display_name="channel123",
    offline_image_url="logo.png",
    profile_image_url="logo.png",
    view_count=42,
)


class TwitchUserFollowResultMock:
    """Mock for twitch user follow result."""

    def __init__(self, follows: list[dict[str, Any]]) -> None:
        """Initialize mock."""
        self.total = len(follows)
        self.data = follows


@dataclass
class UserSubscriptionMock:
    """User subscription mock."""

    broadcaster_id: str
    is_gift: bool


@dataclass
class UserFollowMock:
    """User follow mock."""

    followed_at: str


@dataclass
class StreamMock:
    """Stream mock."""

    game_name: str
    title: str
    thumbnail_url: str


STREAMS = StreamMock(
    game_name="Good game", title="Title", thumbnail_url="stream-medium.png"
)


class TwitchMock:
    """Mock for the twitch object."""

    def __await__(self):
        """Add async capabilities to the mock."""
        t = asyncio.create_task(self._noop())
        yield from t
        return self

    def __init__(
        self,
        is_streaming: bool = True,
        is_gifted: bool = False,
        is_subscribed: bool = False,
        is_following: bool = True,
    ) -> None:
        """Initialize mock."""
        self._is_streaming = is_streaming
        self._is_gifted = is_gifted
        self._is_subscribed = is_subscribed
        self._is_following = is_following

    async def _noop(self):
        """Fake function to create task."""
        pass

    async def get_users(
        self, user_ids: list[str] | None = None, logins: list[str] | None = None
    ) -> AsyncGenerator[TwitchUser, None]:
        """Get list of mock users."""
        for user in [USER_OBJECT]:
            yield user

    def has_required_auth(
        self, required_type: AuthType, required_scope: list[AuthScope]
    ) -> bool:
        """Return if auth required."""
        return True

    async def get_users_follows(
        self, to_id: str | None = None, from_id: str | None = None
    ) -> TwitchUserFollowResultMock:
        """Return the followers of the user."""
        if self._is_following:
            return TwitchUserFollowResultMock(
                follows=[UserFollowMock("2020-01-20T21:22:42") for _ in range(0, 24)]
            )
        return TwitchUserFollowResultMock(follows=[])

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
        self, token: str, scope: list[AuthScope], validate: bool = True
    ) -> None:
        """Set user authentication."""
        pass

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
