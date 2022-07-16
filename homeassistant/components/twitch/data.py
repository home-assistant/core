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

    data: list[dict]
    pagination: TwitchResponsePagination | None = None
    total: int | None = None


@dataclass
class TwitchStream:
    """Twitch Stream."""

    id: str
    user_id: str
    user_name: str
    game_id: str
    type: str
    title: str
    viewer_count: int
    started_at: str
    language: str
    thumbnail_url: str
    tag_ids: list[str]


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
class TwitchChannel(TwitchUser):
    """Twitch Channel."""

    followers: int
    subscriptions: TwitchResponse
    stream: TwitchStream | None = None


@dataclass
class TwitchCoordinatorData:
    """Twitch Coordianator Data."""

    channels: list[TwitchChannel]
    user: TwitchUser
