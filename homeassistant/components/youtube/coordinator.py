"""DataUpdateCoordinator for the YouTube integration."""

import asyncio
from datetime import timedelta
from typing import Any, Final, override

from youtubeaio.types import UnauthorizedError, YouTubeBackendError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AsyncConfigEntryAuth
from .const import (
    ATTR_DESCRIPTION,
    ATTR_IS_SHORT,
    ATTR_LATEST_SHORT,
    ATTR_LATEST_VIDEO,
    ATTR_LATEST_VIDEO_NON_SHORT,
    ATTR_PUBLISHED_AT,
    ATTR_SUBSCRIBER_COUNT,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    ATTR_TOTAL_VIEWS,
    ATTR_VIDEO_COUNT,
    ATTR_VIDEO_ID,
    CONF_CHANNELS,
    DOMAIN,
    LOGGER,
)

type YouTubeConfigEntry = ConfigEntry[YouTubeDataUpdateCoordinator]

# Twice youtubeaio's 10s per-call timeout: single slow calls are handled by
# the library's own timeout (backend error / non-Short fallback); this budget
# only aborts the serial accumulation of several slow checks per channel.
_SHORTS_DETECTION_TIMEOUT: Final = 20


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

    config_entry: YouTubeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: YouTubeConfigEntry,
        auth: AsyncConfigEntryAuth,
    ) -> None:
        """Initialize the YouTube data coordinator."""
        self._auth = auth
        self._is_short_cache: dict[str, bool] = {}
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        youtube = await self._auth.get_resource()
        res = {}
        channel_ids = self.config_entry.options[CONF_CHANNELS]
        try:
            async for channel in youtube.get_channels(channel_ids):
                checked = 0
                latest_video: dict[str, Any] | None = None
                latest_short: dict[str, Any] | None = None
                latest_video_non_short: dict[str, Any] | None = None
                try:
                    async with asyncio.timeout(_SHORTS_DETECTION_TIMEOUT):
                        # Only examine the first page (10 items): paginating
                        # further burns API quota for no benefit.
                        async for video in youtube.get_playlist_items(
                            channel.upload_playlist_id, 10
                        ):
                            checked += 1
                            is_short = await self._resolve_is_short(youtube, video)
                            entry = _build_video_dict(video, is_short)
                            if latest_video is None:
                                latest_video = entry
                            if is_short and latest_short is None:
                                latest_short = entry
                            if not is_short and latest_video_non_short is None:
                                latest_video_non_short = entry
                            if (
                                latest_short is not None
                                and latest_video_non_short is not None
                            ):
                                break
                            if checked >= 10:
                                break
                except TimeoutError:
                    LOGGER.warning(
                        "Timed out processing recent uploads for channel %s; "
                        "continuing with partial results",
                        channel.channel_id,
                    )
                LOGGER.debug(
                    "Examined %d videos for channel %s", checked, channel.channel_id
                )

                res[channel.channel_id] = {
                    ATTR_ID: channel.channel_id,
                    ATTR_TITLE: channel.snippet.title,
                    ATTR_ICON: channel.snippet.thumbnails.get_highest_quality().url,
                    ATTR_LATEST_VIDEO: latest_video,
                    ATTR_LATEST_SHORT: latest_short,
                    ATTR_LATEST_VIDEO_NON_SHORT: latest_video_non_short,
                    ATTR_SUBSCRIBER_COUNT: channel.statistics.subscriber_count,
                    ATTR_TOTAL_VIEWS: channel.statistics.view_count,
                    ATTR_VIDEO_COUNT: channel.statistics.video_count,
                }
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except YouTubeBackendError as err:
            raise UpdateFailed("Couldn't connect to YouTube") from err
        return res

    async def _resolve_is_short(self, youtube: Any, video: Any) -> bool:
        """Return whether a single video is a Short.

        Uses the cache when available. Videos can stop being checked as soon
        as both a Short and a non-Short have been found. On error the result
        is treated as non-Short without caching so the next refresh can retry.
        """
        video_id = video.content_details.video_id
        if video_id in self._is_short_cache:
            return self._is_short_cache[video_id]
        try:
            result = await youtube.is_short(video_id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Error determining if video %s is a Short; treating as non-Short: %s",
                video_id,
                exc,
            )
            return False
        is_short = bool(result)
        self._is_short_cache[video_id] = is_short
        return is_short
