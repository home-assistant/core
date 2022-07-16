"""Data ckasses for Twitch."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TwitchResponsePagination:
    """Twitch Response Pagination."""

    cursor: str | None = None


@dataclass
class TwitchResponse:
    """Twitch Response."""

    data: list[dict] | None = None
    error: str | None = None
    message: str | None = None
    pagination: dict | None = None
    status: str | None = None
    total: int | None = None


@dataclass
class TwitchStream:
    """Twitch Stream."""

    id: str
    game_id: str
    game_name: str
    is_mature: bool
    language: str
    started_at: str
    tag_ids: list[str]
    thumbnail_url: str
    title: str
    type: str
    user_id: str
    user_login: str
    user_name: str
    viewer_count: int


@dataclass
class TwitchUser:
    """Twitch User."""

    id: str
    login: str
    display_name: str
    type: str
    broadcaster_type: str
    description: str
    profile_image_url: str
    offline_image_url: str
    view_count: int
    created_at: str


@dataclass
class TwitchFollower:
    """Twitch Follower."""

    from_id: str
    from_login: str
    from_name: str
    to_id: str
    to_login: str
    to_name: str
    followed_at: str


@dataclass
class TwitchSubscription:
    """Twitch Subscription."""

    broadcaster_id: str
    broadcaster_name: str
    broadcaster_login: str
    is_gift: bool
    tier: str


@dataclass
class TwitchChannel(TwitchUser):
    """Twitch Channel."""

    followers: int | None = None
    following: TwitchFollower | None = None
    subscription: TwitchSubscription | None = None
    stream: TwitchStream | None = None


@dataclass
class TwitchCoordinatorData:
    """Twitch Coordianator Data."""

    channels: list[TwitchChannel]
    user: TwitchUser
