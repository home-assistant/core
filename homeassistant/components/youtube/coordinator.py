"""DataUpdateCoordinator for the YouTube integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import aiohttp
from youtubeaio.types import UnauthorizedError, YouTubeBackendError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import AsyncConfigEntryAuth
from .const import (
    ATTR_DESCRIPTION,
    ATTR_IS_SHORT,
    ATTR_LATEST_SHORT,
    ATTR_LATEST_UPLOAD,
    ATTR_LATEST_VIDEO_NON_SHORT,
    ATTR_PUBLISHED_AT,
    ATTR_SUBSCRIBER_COUNT,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    ATTR_TOTAL_VIEWS,
    ATTR_VIDEO_ID,
    CONF_CHANNELS,
    DOMAIN,
    LOGGER,
)

# Use fake curl's User-Agent to avoid YouTube GDPR consent redirects triggered by unknown clients.
_YOUTUBE_HEADERS = {"User-Agent": "curl/x.x"}


async def _is_youtube_short(session: aiohttp.ClientSession, video_id: str) -> bool:
    """Detect whether a video is a YouTube Short.

    Sends a HEAD request to the /shorts/{id} endpoint (no redirect follow).
    - HTTP 200 → the Shorts page exists → IS a Short.
    - HTTP 303 → redirected to /watch?v=… → NOT a Short.
    Any network error defaults to False (treat as regular video).
    """

    LOGGER.debug("Checking if video %s is a Short", video_id)
    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        async with session.head(
            url,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status == 200:
                LOGGER.debug("Video %s is a Short (200)", video_id)
                return True
            if resp.status in (302, 303):
                # Non-Short : YouTube redirige vers /watch?v=...
                LOGGER.debug(
                    "Video %s is not a Short (%d) => redirect to %s",
                    video_id,
                    resp.status,
                    resp.headers.get("Location", ""),
                )
                return False
    except (TimeoutError, aiohttp.ClientError) as err:
        LOGGER.debug("Could not determine if %s is a Short: %s", video_id, err)
    return False


def _build_video_dict(video: Any, is_short: bool) -> dict[str, Any]:
    """Build the video attribute dict shared by all video sensors."""

    return {
        ATTR_PUBLISHED_AT: video.snippet.added_at,
        ATTR_TITLE: video.snippet.title,
        ATTR_DESCRIPTION: video.snippet.description,
        ATTR_THUMBNAIL: video.snippet.thumbnails.get_highest_quality().url,
        ATTR_VIDEO_ID: video.content_details.video_id,
        ATTR_IS_SHORT: is_short,
    }


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """A YouTube Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, auth: AsyncConfigEntryAuth
    ) -> None:
        """Initialize the YouTube data coordinator."""
        self._auth = auth
        self._session: aiohttp.ClientSession | None = None
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def async_shutdown(self) -> None:
        """Close the aiohttp session on shutdown."""
        await super().async_shutdown()
        if self._session and not self._session.closed:
            await self._session.close()

    async def _async_update_data(self) -> dict[str, Any]:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=_YOUTUBE_HEADERS,
            )

        youtube = await self._auth.get_resource()
        res = {}
        channel_ids = self.config_entry.options[CONF_CHANNELS]
        try:
            async for channel in youtube.get_channels(channel_ids):
                # Fetch up to 10 recent videos to find a Short and a non-Short.
                videos = [
                    v
                    async for v in youtube.get_playlist_items(
                        channel.upload_playlist_id, 10
                    )
                ]
                LOGGER.debug(
                    "Fetched %d videos for channel %s", len(videos), channel.channel_id
                )
                # Detect Shorts concurrently to minimise latency.
                is_short_flags = await asyncio.gather(
                    *[
                        _is_youtube_short(self._session, v.content_details.video_id)
                        for v in videos
                    ]
                )
                latest_upload: dict[str, Any] | None = None
                latest_short: dict[str, Any] | None = None
                latest_video_non_short: dict[str, Any] | None = None
                for video, is_short in zip(videos, is_short_flags, strict=False):
                    entry = _build_video_dict(video, is_short)
                    if latest_upload is None:
                        latest_upload = entry
                    if is_short and latest_short is None:
                        latest_short = entry
                    if not is_short and latest_video_non_short is None:
                        latest_video_non_short = entry
                    if latest_short is not None and latest_video_non_short is not None:
                        break

                res[channel.channel_id] = {
                    ATTR_ID: channel.channel_id,
                    ATTR_TITLE: channel.snippet.title,
                    ATTR_ICON: channel.snippet.thumbnails.get_highest_quality().url,
                    ATTR_LATEST_UPLOAD: latest_upload,
                    ATTR_LATEST_SHORT: latest_short,
                    ATTR_LATEST_VIDEO_NON_SHORT: latest_video_non_short,
                    ATTR_SUBSCRIBER_COUNT: channel.statistics.subscriber_count,
                    ATTR_TOTAL_VIEWS: channel.statistics.view_count,
                }
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except YouTubeBackendError as err:
            raise UpdateFailed("Couldn't connect to YouTube") from err
        return res
