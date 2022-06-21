"""UniFi Protect media sources."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import cast

import pytz
from pyunifiprotect.data import Event, EventType
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_VIDEO,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .data import ProtectData
from .views import async_generate_event_video_url, async_generate_thumbnail_url

VIDEO_FORMAT = "video/mp4"


class SimpleEventType(str, Enum):
    """Enum to Camera Video events."""

    ALL = "All Events"
    RING = "Ring Events"
    MOTION = "Motion Events"
    SMART = "Smart Detections"

    @classmethod
    def get_from_name(cls, name: str) -> SimpleEventType:
        """Get SimpleEventType from name."""

        if name.lower() == "smart_detect":
            return SimpleEventType.SMART

        types: list[SimpleEventType] = list(cls)
        for event_type in types:
            if event_type.name.lower() == name.lower():
                return event_type
        raise ValueError("Invalid event_type")

    @classmethod
    def get_event_type(cls, event_type: SimpleEventType) -> EventType | None:
        """Get UniFi Protect event type from SimpleEventType."""

        if event_type == SimpleEventType.ALL:
            return None
        if event_type == SimpleEventType.RING:
            return EventType.RING
        if event_type == SimpleEventType.MOTION:
            return EventType.MOTION
        return EventType.SMART_DETECT


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up UniFi Protect media source."""

    data_sources: dict[str, ProtectData] = {}
    for data in hass.data[DOMAIN].values():
        if isinstance(data, ProtectData):
            data_sources[data.api.bootstrap.nvr.id] = data

    return ProtectMediaSource(hass, data_sources)


@callback
def _timezone(hass: HomeAssistant) -> timezone:
    return cast(timezone, pytz.timezone(hass.config.time_zone))


@callback
def _localize_dt(hass: HomeAssistant, timestamp: datetime) -> datetime:
    return timestamp.astimezone(_timezone(hass))


@callback
def _now(hass: HomeAssistant) -> datetime:
    return _localize_dt(hass, datetime.utcnow())


@callback
def _get_start_end(hass: HomeAssistant, start: datetime) -> tuple[datetime, datetime]:
    start = _localize_dt(hass, start)
    end = _now(hass)

    start = start.replace(day=1, hour=1, minute=0, second=0, microsecond=0)
    end = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return start, end


@callback
def _bad_identifier(identifier: str, err: Exception | None = None) -> BrowseMediaSource:
    msg = f"Unexpected identifier: {identifier}"
    if err is None:
        raise BrowseError(msg)
    raise BrowseError(msg) from err


@callback
def _bad_identifier_media(identifier: str, err: Exception | None = None) -> PlayMedia:
    return cast(PlayMedia, _bad_identifier(identifier, err))


@callback
def _format_duration(duration: timedelta) -> str:
    formatted = ""
    seconds = int(duration.total_seconds())
    if seconds > 3600:
        hours = seconds // 3600
        formatted += f"{hours}h "
        seconds -= hours * 3600
    if seconds > 60:
        minutes = seconds // 60
        formatted += f"{minutes}m "
        seconds -= minutes * 60
    if seconds > 0:
        formatted += f"{seconds}s "

    return formatted.strip()


class ProtectMediaSource(MediaSource):
    """Represents all UniFi Protect NVRs."""

    name: str = "UniFi Protect"

    def __init__(
        self, hass: HomeAssistant, data_sources: dict[str, ProtectData]
    ) -> None:
        """Initialize the UniFi Protect media source."""

        super().__init__(DOMAIN)
        self.hass = hass
        self.data_sources = data_sources

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Return a streamable URL and associated mime type for a UniFi Protect event.

        Accepted identifier format are

        * {nvr_id}:event:{event_id} - MP4 video clip for specific event
        * {nvr_id}:eventthumb:{event_id} - Thumbnail JPEG for specific event
        """

        parts = item.identifier.split(":")
        if len(parts) != 3 or parts[1] not in ("event", "eventthumb"):
            return _bad_identifier_media(item.identifier)

        thumbnail_only = parts[1] == "eventthumb"
        try:
            data = self.data_sources[parts[0]]
        except IndexError as err:
            return _bad_identifier_media(item.identifier, err)

        try:
            event = await data.api.get_event(parts[2])
        except NvrError as err:
            return _bad_identifier_media(item.identifier, err)

        if thumbnail_only:
            PlayMedia(async_generate_thumbnail_url(event), "image/jpeg")
        return PlayMedia(async_generate_event_video_url(event), "video/mp4")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return a browsable UniFi Protect media source.

        Identifier formatters for UniFi Protect media sources are all in IDs from
        the UniFi Protect instance since events may not always map 1:1 to a Home
        Assistant device or entity. It also drasically speeds up resolution.

        Accepted identifier formats:

        * {nvr_id} - Root NVR source
        * {nvr_id}:event:{event_id} - Specific Event for NVR
        * {nvr_id}:eventthumb:{event_id} - Specific Event Thumbnail for NVR
        * {nvr_id}:all|{camera_id} - Root Camera(s) source
        * {nvr_id}:all|{camera_id}:all|{event_type} - Root Camera(s) Event Type(s) source
        * {nvr_id}:all|{camera_id}:all|{event_type}:day:{day_count} - Listing of all events
            in last {day_count}, sorted in reverse chronological order
        * {nvr_id}:all|{camera_id}:all|{event_type}:month:{year}:{month} - Listing of all
            events for give {month} + {year} combination in chronological order
        """

        if not item.identifier:
            return await self._build_sources()

        parts = item.identifier.split(":")

        try:
            data = self.data_sources[parts[0]]
        except IndexError as err:
            return _bad_identifier(item.identifier, err)

        # {nvr_id}
        if len(parts) == 1:
            return await self._build_console(data)

        # {nvr_id}:event:{id}
        if len(parts) == 3 and parts[1] in ("event", "eventthumb"):
            thumbnail_only = parts[1] == "eventthumb"
            return await self._resolve_event(data, parts[2], thumbnail_only)

        # {nvr_id}:all|{camera_id}
        camera_id = parts[1]
        if len(parts) == 2:
            return await self._build_camera(data, camera_id, build_children=True)

        # {nvr_id}:all|{camera_id}:all|{event_type}
        try:
            event_type = SimpleEventType.get_from_name(parts[2])
        except (IndexError, ValueError) as err:
            return _bad_identifier(item.identifier, err)

        if len(parts) == 3:
            return await self._build_events_type(
                data, camera_id, event_type, build_children=True
            )

        # {nvr_id}:all|{camera_id}:all|{event_type}:day:{day_count}
        if parts[3] == "day":
            try:
                days = int(parts[4])
            except (IndexError, ValueError) as err:
                return _bad_identifier(item.identifier, err)

            return await self._build_day(
                data, camera_id, event_type, days, build_children=True
            )

        # {nvr_id}:all|{camera_id}:all|{event_type}:month:{year}:{month}
        if parts[3] == "month":
            try:
                year = int(parts[4])
                month = int(parts[5])
            except (IndexError, ValueError) as err:
                return _bad_identifier(item.identifier, err)

            start = date(year=year, month=month, day=1)
            return await self._build_month(
                data, camera_id, event_type, start, build_children=True
            )

        return _bad_identifier(item.identifier)

    async def _resolve_event(
        self, data: ProtectData, event_id: str, thumbnail_only: bool = False
    ) -> BrowseMediaSource:
        """Resolve a specific event."""

        subtype = "eventthumb" if thumbnail_only else "event"
        try:
            event = await data.api.get_event(event_id)
        except NvrError as err:
            return _bad_identifier(
                f"{data.api.bootstrap.nvr.id}:{subtype}:{event_id}", err
            )

        if event.start is None or event.end is None:
            raise BrowseError("Event is still ongoing")

        return await self._build_event(data, event, thumbnail_only)

    async def _build_event(
        self, data: ProtectData, event: Event, thumbnail_only: bool = False
    ) -> BrowseMediaSource:
        """Build media source for event."""

        assert event.start is not None
        assert event.end is not None

        title = event.start.astimezone(_timezone(self.hass)).strftime("%x %X")
        duration = event.end - event.start
        title += f" {_format_duration(duration)}"
        if event.type == EventType.RING:
            event_type = "Ring Event"
        elif event.type == EventType.MOTION:
            event_type = "Motion Event"
        elif event.type == EventType.SMART_DETECT:
            event_type = f"Smart Detection - {event.smart_detect_types[0].name.title()}"
        title += f" {event_type}"

        if thumbnail_only:
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{data.api.bootstrap.nvr.id}:eventthumb:{event.id}",
                media_class=MEDIA_CLASS_IMAGE,
                media_content_type="image/jpeg",
                title=title,
                can_play=True,
                can_expand=False,
                thumbnail=async_generate_thumbnail_url(event, 185, 185),
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{data.api.bootstrap.nvr.id}:event:{event.id}",
            media_class=MEDIA_CLASS_VIDEO,
            media_content_type="video/mp4",
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=async_generate_thumbnail_url(event, 185, 185),
        )

    async def _build_events(
        self,
        data: ProtectData,
        start: datetime,
        end: datetime,
        camera_id: str | None = None,
        event_type: EventType | None = None,
        reserve: bool = False,
    ) -> list[BrowseMediaSource]:
        """Build media source for actual events."""

        if event_type is None:
            types = [
                EventType.RING,
                EventType.MOTION,
                EventType.SMART_DETECT,
            ]
        else:
            types = [event_type]

        sources: list[BrowseMediaSource] = []
        events = await data.api.get_events(start=start, end=end, types=types)
        events = sorted(events, key=lambda e: e.start, reverse=reserve)
        for event in events:
            # do not process ongoing events
            if event.start is None or event.end is None:
                continue

            if camera_id is not None and event.camera_id != camera_id:
                continue

            # smart detect events have a paired motion event
            if event.type == EventType.MOTION and len(event.smart_detect_events) > 0:
                continue

            sources.append(await self._build_event(data, event))

        return sources

    async def _build_day(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        days: int,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for events in relative days."""

        base_id = f"{data.api.bootstrap.nvr.id}:{camera_id}:{event_type.name.lower()}"
        title = f"Last {days} Days"
        if days == 1:
            title = "Last 24 Hours"

        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{base_id}:day:{days}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="video/mp4",
            title=title,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
        )

        if build_children:
            now = _now(self.hass)

            args = {
                "data": data,
                "start": now - timedelta(days=days),
                "end": now,
                "reserve": True,
            }
            if camera_id != "all":
                args["camera_id"] = camera_id
            if event_type != SimpleEventType.ALL:
                args["event_type"] = SimpleEventType.get_event_type(event_type)

            source.children = await self._build_events(**args)  # type: ignore[arg-type,assignment]

        return source

    async def _build_month(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        start: date,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for events for a given month."""

        base_id = f"{data.api.bootstrap.nvr.id}:{camera_id}:{event_type.name.lower()}"

        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{base_id}:month:{start.year}:{start.month}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=f"{start.strftime('%B %Y')}",
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
        )

        if build_children:
            start_dt = datetime(
                year=start.year,
                month=start.month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                tzinfo=_timezone(self.hass),
            )
            if start_dt.month < 12:
                end_dt = start_dt.replace(month=start_dt.month + 1)
            else:
                end_dt = start_dt.replace(year=start_dt.year + 1, month=1)

            args = {
                "data": data,
                "start": start_dt,
                "end": end_dt,
                "reserve": False,
            }
            if camera_id != "all":
                args["camera_id"] = camera_id
            if event_type != SimpleEventType.ALL:
                args["event_type"] = SimpleEventType.get_event_type(event_type)

            source.children = await self._build_events(**args)  # type: ignore[arg-type,assignment]

        return source

    async def _build_events_type(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for a specific event type."""

        base_id = f"{data.api.bootstrap.nvr.id}:{camera_id}:{event_type.name.lower()}"

        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=base_id,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=event_type.value.title(),
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
        )

        if build_children and data.api.bootstrap.recording_start is not None:
            children = [
                self._build_day(data, camera_id, event_type, 1),
                self._build_day(data, camera_id, event_type, 7),
                self._build_day(data, camera_id, event_type, 30),
            ]

            start, end = _get_start_end(self.hass, data.api.bootstrap.recording_start)
            while end > start:
                children.append(
                    self._build_month(data, camera_id, event_type, end.date())
                )
                end = (end - timedelta(days=1)).replace(day=1)
            source.children = await asyncio.gather(*children)

        return source

    async def _build_camera(
        self, data: ProtectData, camera_id: str, build_children: bool = False
    ) -> BrowseMediaSource:
        """Build media source for a single UniFi Protect Camera."""

        name = "All Cameras"
        is_doorbell = data.api.bootstrap.has_doorbell
        has_smart = data.api.bootstrap.has_smart_detections
        if camera_id != "all":
            camera = data.api.bootstrap.cameras.get(camera_id)
            if camera is None:
                raise BrowseError(f"Unknown Camera ID: {camera_id}")
            name = camera.name or camera.market_name or camera.type
            is_doorbell = camera.feature_flags.has_chime
            has_smart = camera.feature_flags.has_smart_detect

        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{data.api.bootstrap.nvr.id}:{camera_id}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=name,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
        )

        if build_children:
            source.children = [
                await self._build_events_type(data, camera_id, SimpleEventType.MOTION),
            ]

            if is_doorbell:
                source.children.insert(
                    0,
                    await self._build_events_type(
                        data, camera_id, SimpleEventType.RING
                    ),
                )

            if has_smart:
                source.children.append(
                    await self._build_events_type(
                        data, camera_id, SimpleEventType.SMART
                    )
                )

            if is_doorbell or has_smart:
                source.children.insert(
                    0,
                    await self._build_events_type(data, camera_id, SimpleEventType.ALL),
                )

        return source

    async def _build_cameras(self, data: ProtectData) -> list[BrowseMediaSource]:
        """Build media source for a single UniFi Protect NVR."""

        cameras: list[BrowseMediaSource] = [await self._build_camera(data, "all")]

        for camera in data.api.bootstrap.cameras.values():
            if not camera.can_read_media(data.api.bootstrap.auth_user):
                continue
            cameras.append(await self._build_camera(data, camera.id))

        return cameras

    async def _build_console(self, data: ProtectData) -> BrowseMediaSource:
        """Build media source for a single UniFi Protect NVR."""

        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{data.api.bootstrap.nvr.id}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=data.api.bootstrap.nvr.name,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
            children=await self._build_cameras(data),
        )

        return base

    async def _build_sources(self) -> BrowseMediaSource:
        """Return all media source for all UniFi Protect NVRs."""

        consoles: list[BrowseMediaSource] = []
        for data_source in self.data_sources.values():
            if not data_source.api.bootstrap.has_media:
                continue
            console_source = await self._build_console(data_source)
            if console_source.children is None or len(console_source.children) == 0:
                continue
            consoles.append(console_source)

        if len(consoles) == 1:
            return consoles[0]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
            children=consoles,
        )
