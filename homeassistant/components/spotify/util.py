"""Utils for Spotify."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate

from spotifyaio import Image
import yarl

from .const import MEDIA_PLAYER_PREFIX
from .entity import SpotifyEntity


def is_spotify_media_type(media_content_type: str) -> bool:
    """Return whether the media_content_type is a valid Spotify media_id."""
    return media_content_type.startswith(MEDIA_PLAYER_PREFIX)


def resolve_spotify_media_type(media_content_type: str) -> str:
    """Return actual spotify media_content_type."""
    return media_content_type.removeprefix(MEDIA_PLAYER_PREFIX)


def fetch_image_url(images: list[Image]) -> str | None:
    """Fetch image url."""
    if not images:
        return None
    return images[0].url


def spotify_uri_from_media_browser_url(media_content_id: str) -> str:
    """Extract spotify URI from media browser URL."""
    if media_content_id and media_content_id.startswith(MEDIA_PLAYER_PREFIX):
        parsed_url = yarl.URL(media_content_id)
        media_content_id = parsed_url.name
    return media_content_id


AFTER_REQUEST_SLEEP = 1


def async_refresh_after[_T: SpotifyEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to yield and refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        await asyncio.sleep(AFTER_REQUEST_SLEEP)
        await self.coordinator.async_refresh()

    return _async_wrap
