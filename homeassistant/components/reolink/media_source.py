"""Expose Reolink IP camera VODs as media sources."""

from __future__ import annotations

import datetime as dt
import logging

from reolink_aio.enums import VodRequestType

from homeassistant.components.camera import DOMAIN as CAM_DOMAIN, DynamicStreamSettings
from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.components.stream import create_stream
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ReolinkData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> ReolinkVODMediaSource:
    """Set up camera media source."""
    return ReolinkVODMediaSource(hass)


def res_name(stream: str) -> str:
    """Return the user friendly name for a stream."""
    return "High res." if stream == "main" else "Low res."


class ReolinkVODMediaSource(MediaSource):
    """Provide Reolink camera VODs as media sources."""

    name: str = "Reolink"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ReolinkVODMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.data: dict[str, ReolinkData] = hass.data[DOMAIN]

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        identifier = item.identifier.split("|", 5)
        if identifier[0] != "FILE":
            raise Unresolvable(f"Unknown media item '{item.identifier}'.")

        _, config_entry_id, channel_str, stream_res, filename = identifier
        channel = int(channel_str)

        host = self.data[config_entry_id].host

        vod_type = VodRequestType.RTMP
        if host.api.is_nvr:
            vod_type = VodRequestType.FLV

        mime_type, url = await host.api.get_vod_source(
            channel, filename, stream_res, vod_type
        )
        if _LOGGER.isEnabledFor(logging.DEBUG):
            url_log = f"{url.split('&user=')[0]}&user=xxxxx&password=xxxxx"
            _LOGGER.debug(
                "Opening VOD stream from %s: %s", host.api.camera_name(channel), url_log
            )

        stream = create_stream(self.hass, url, {}, DynamicStreamSettings())
        stream.add_provider("hls", timeout=3600)
        stream_url: str = stream.endpoint_url("hls")
        stream_url = stream_url.replace("master_", "")
        return PlayMedia(stream_url, mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier is None:
            return await self._async_generate_root()

        identifier = item.identifier.split("|", 7)
        item_type = identifier[0]

        if item_type == "CAM":
            _, config_entry_id, channel_str = identifier
            return await self._async_generate_resolution_select(
                config_entry_id, int(channel_str)
            )
        if item_type == "RES":
            _, config_entry_id, channel_str, stream = identifier
            return await self._async_generate_camera_days(
                config_entry_id, int(channel_str), stream
            )
        if item_type == "DAY":
            (
                _,
                config_entry_id,
                channel_str,
                stream,
                year_str,
                month_str,
                day_str,
            ) = identifier
            return await self._async_generate_camera_files(
                config_entry_id,
                int(channel_str),
                stream,
                int(year_str),
                int(month_str),
                int(day_str),
            )

        raise Unresolvable(f"Unknown media item '{item.identifier}' during browsing.")

    async def _async_generate_root(self) -> BrowseMediaSource:
        """Return all available reolink cameras as root browsing structure."""
        children: list[BrowseMediaSource] = []

        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        for config_entry in self.hass.config_entries.async_entries(DOMAIN):
            if config_entry.state != ConfigEntryState.LOADED:
                continue
            channels: list[str] = []
            host = self.data[config_entry.entry_id].host
            entities = er.async_entries_for_config_entry(
                entity_reg, config_entry.entry_id
            )
            for entity in entities:
                if (
                    entity.disabled
                    or entity.device_id is None
                    or entity.domain != CAM_DOMAIN
                ):
                    continue

                device = device_reg.async_get(entity.device_id)
                ch = entity.unique_id.split("_")[1]
                if ch in channels or device is None:
                    continue
                channels.append(ch)

                if (
                    host.api.api_version("recReplay", int(ch)) < 1
                    or not host.api.hdd_info
                ):
                    # playback stream not supported by this camera or no storage installed
                    continue

                device_name = device.name
                if device.name_by_user is not None:
                    device_name = device.name_by_user

                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"CAM|{config_entry.entry_id}|{ch}",
                        media_class=MediaClass.CHANNEL,
                        media_content_type=MediaType.PLAYLIST,
                        title=device_name,
                        thumbnail=f"/api/camera_proxy/{entity.entity_id}",
                        can_play=False,
                        can_expand=True,
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Reolink",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _async_generate_resolution_select(
        self, config_entry_id: str, channel: int
    ) -> BrowseMediaSource:
        """Allow the user to select the high or low playback resolution, (low loads faster)."""
        host = self.data[config_entry_id].host

        main_enc = await host.api.get_encoding(channel, "main")
        if main_enc == "h265":
            _LOGGER.debug(
                "Reolink camera %s uses h265 encoding for main stream,"
                "playback only possible using sub stream",
                host.api.camera_name(channel),
            )
            return await self._async_generate_camera_days(
                config_entry_id, channel, "sub"
            )

        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"RES|{config_entry_id}|{channel}|sub",
                media_class=MediaClass.CHANNEL,
                media_content_type=MediaType.PLAYLIST,
                title="Low resolution",
                can_play=False,
                can_expand=True,
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"RES|{config_entry_id}|{channel}|main",
                media_class=MediaClass.CHANNEL,
                media_content_type=MediaType.PLAYLIST,
                title="High resolution",
                can_play=False,
                can_expand=True,
            ),
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"RESs|{config_entry_id}|{channel}",
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.PLAYLIST,
            title=host.api.camera_name(channel),
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _async_generate_camera_days(
        self, config_entry_id: str, channel: int, stream: str
    ) -> BrowseMediaSource:
        """Return all days on which recordings are available for a reolink camera."""
        host = self.data[config_entry_id].host

        # We want today of the camera, not necessarily today of the server
        now = host.api.time() or await host.api.async_get_time()
        start = now - dt.timedelta(days=31)
        end = now

        children: list[BrowseMediaSource] = []
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Requesting recording days of %s from %s to %s",
                host.api.camera_name(channel),
                start,
                end,
            )
        statuses, _ = await host.api.request_vod_files(
            channel, start, end, status_only=True, stream=stream
        )
        for status in statuses:
            for day in status.days:
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"DAY|{config_entry_id}|{channel}|{stream}|{status.year}|{status.month}|{day}",
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaType.PLAYLIST,
                        title=f"{status.year}/{status.month}/{day}",
                        can_play=False,
                        can_expand=True,
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"DAYS|{config_entry_id}|{channel}|{stream}",
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.PLAYLIST,
            title=f"{host.api.camera_name(channel)} {res_name(stream)}",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _async_generate_camera_files(
        self,
        config_entry_id: str,
        channel: int,
        stream: str,
        year: int,
        month: int,
        day: int,
    ) -> BrowseMediaSource:
        """Return all recording files on a specific day of a Reolink camera."""
        host = self.data[config_entry_id].host

        start = dt.datetime(year, month, day, hour=0, minute=0, second=0)
        end = dt.datetime(year, month, day, hour=23, minute=59, second=59)

        children: list[BrowseMediaSource] = []
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Requesting VODs of %s on %s/%s/%s",
                host.api.camera_name(channel),
                year,
                month,
                day,
            )
        _, vod_files = await host.api.request_vod_files(
            channel, start, end, stream=stream
        )
        for file in vod_files:
            file_name = f"{file.start_time.time()} {file.duration}"
            if file.triggers != file.triggers.NONE:
                file_name += " " + " ".join(
                    str(trigger.name).title()
                    for trigger in file.triggers
                    if trigger != trigger.NONE
                )

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"FILE|{config_entry_id}|{channel}|{stream}|{file.file_name}",
                    media_class=MediaClass.VIDEO,
                    media_content_type=MediaType.VIDEO,
                    title=file_name,
                    can_play=True,
                    can_expand=False,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"FILES|{config_entry_id}|{channel}|{stream}",
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.PLAYLIST,
            title=f"{host.api.camera_name(channel)} {res_name(stream)} {year}/{month}/{day}",
            can_play=False,
            can_expand=True,
            children=children,
        )
