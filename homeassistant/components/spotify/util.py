"""Utils for Spotify."""
from __future__ import annotations

from typing import Any

from .const import MEDIA_PLAYER_PREFIX


def is_spotify_media_type(media_content_type: str) -> bool:
    """Return whether the media_content_type is a valid Spotify media_id."""
    return media_content_type.startswith(MEDIA_PLAYER_PREFIX)


def resolve_spotify_media_type(media_content_type: str) -> str:
    """Return actual spotify media_content_type."""
    return media_content_type[len(MEDIA_PLAYER_PREFIX) :]


def fetch_image_url(item: dict[str, Any], key="images") -> str | None:
    """Fetch image url."""
    try:
        return item.get(key, [])[0].get("url")
    except IndexError:
        return None
