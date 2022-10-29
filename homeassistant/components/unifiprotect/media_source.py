"""UniFi Protect media sources."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, cast

from pyunifiprotect.data import (
    Camera,
    Event,
    EventType,
    ModelType,
    SmartDetectObjectType,
)
from pyunifiprotect.exceptions import NvrError
from pyunifiprotect.utils import from_js_time
from yarl import URL

from homeassistant.components.camera import CameraImageView
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .data import ProtectData
from .views import async_generate_event_video_url, async_generate_thumbnail_url

VIDEO_FORMAT = "video/mp4"
THUMBNAIL_WIDTH = 185
THUMBNAIL_HEIGHT = 185


class SimpleEventType(str, Enum):
    """Enum to Camera Video events."""

    ALL = "all"
    RING = "ring"
    MOTION = "motion"
    SMART = "smart"


class IdentifierType(str, Enum):
    """UniFi Protect identifier type."""

    EVENT = "event"
    EVENT_THUMB = "eventthumb"
    BROWSE = "browse"


class IdentifierTimeType(str, Enum):
    """UniFi Protect identifier subtype."""

    RECENT = "recent"
    RANGE = "range"


EVENT_MAP = {
    SimpleEventType.ALL: None,
    SimpleEventType.RING: EventType.RING,
    SimpleEventType.MOTION: EventType.MOTION,
    SimpleEventType.SMART: EventType.SMART_DETECT,
}
EVENT_NAME_MAP = {
    SimpleEventType.ALL: "All Events",
    SimpleEventType.RING: "Ring Events",
    SimpleEventType.MOTION: "Motion Events",
    SimpleEventType.SMART: "Smart Detections",
}


def get_ufp_event(event_type: SimpleEventType) -> EventType | None:
    """Get UniFi Protect event type from SimpleEventType."""

    return EVENT_MAP[event_type]


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up UniFi Protect media source."""

    data_sources: dict[str, ProtectData] = {}
    for data in hass.data.get(DOMAIN, {}).values():
        if isinstance(data, ProtectData):
            data_sources[data.api.bootstrap.nvr.id] = data

    return ProtectMediaSource(hass, data_sources)


@callback
def _get_month_start_end(start: datetime) -> tuple[datetime, datetime]:
    start = dt_util.as_local(start)
    end = dt_util.now()

    start = start.replace(day=1, hour=0, minute=0, second=1, microsecond=0)
    end = end.replace(day=1, hour=0, minute=0, second=2, microsecond=0)

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
    _registry: er.EntityRegistry | None

    def __init__(
        self, hass: HomeAssistant, data_sources: dict[str, ProtectData]
    ) -> None:
        """Initialize the UniFi Protect media source."""

        super().__init__(DOMAIN)
        self.hass = hass
        self.data_sources = data_sources
        self._registry = None

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
        except (KeyError, IndexError) as err:
            return _bad_identifier_media(item.identifier, err)

        event = data.api.bootstrap.events.get(parts[2])
        if event is None:
            try:
                event = await data.api.get_event(parts[2])
            except NvrError as err:
                return _bad_identifier_media(item.identifier, err)
            else:
                # cache the event for later
                data.api.bootstrap.events[event.id] = event

        nvr = data.api.bootstrap.nvr
        if thumbnail_only:
            return PlayMedia(
                async_generate_thumbnail_url(event.id, nvr.id), "image/jpeg"
            )
        return PlayMedia(async_generate_event_video_url(event), "video/mp4")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return a browsable UniFi Protect media source.

        Identifier formatters for UniFi Protect media sources are all in IDs from
        the UniFi Protect instance since events may not always map 1:1 to a Home
        Assistant device or entity. It also drasically speeds up resolution.

        The UniFi Protect Media source is timebased for the events recorded by the NVR.
        So its structure is a bit different then many other media players. All browsable
        media is a video clip. The media source could be greatly cleaned up if/when the
        frontend has filtering supporting.

        * ... Each NVR Console (hidden if there is only one)
            * All Cameras
            * ... Camera X
                * All Events
                * ... Event Type X
                    * Last 24 Hours -> Events
                    * Last 7 Days -> Events
                    * Last 30 Days -> Events
                    * ... This Month - X
                        * Whole Month -> Events
                        * ... Day X -> Events

        Accepted identifier formats:

        * {nvr_id}:event:{event_id}
            Specific Event for NVR
        * {nvr_id}:eventthumb:{event_id}
            Specific Event Thumbnail for NVR
        * {nvr_id}:browse
            Root NVR browse source
        * {nvr_id}:browse:all|{camera_id}
            Root Camera(s) browse source
        * {nvr_id}:browse:all|{camera_id}:all|{event_type}
            Root Camera(s) Event Type(s) browse source
        * {nvr_id}:browse:all|{camera_id}:all|{event_type}:recent:{day_count}
            Listing of all events in last {day_count}, sorted in reverse chronological order
        * {nvr_id}:browse:all|{camera_id}:all|{event_type}:range:{year}:{month}
            List of folders for each day in month + all events for month
        * {nvr_id}:browse:all|{camera_id}:all|{event_type}:range:{year}:{month}:all|{day}
            Listing of all events for give {day} + {month} + {year} combination in chronological order
        """

        if not item.identifier:
            return await self._build_sources()

        parts = item.identifier.split(":")

        try:
            data = self.data_sources[parts[0]]
        except (KeyError, IndexError) as err:
            return _bad_identifier(item.identifier, err)

        if len(parts) < 2:
            return _bad_identifier(item.identifier)

        try:
            identifier_type = IdentifierType(parts[1])
        except ValueError as err:
            return _bad_identifier(item.identifier, err)

        if identifier_type in (IdentifierType.EVENT, IdentifierType.EVENT_THUMB):
            thumbnail_only = identifier_type == IdentifierType.EVENT_THUMB
            return await self._resolve_event(data, parts[2], thumbnail_only)

        # rest are params for browse
        parts = parts[2:]

        # {nvr_id}:browse
        if len(parts) == 0:
            return await self._build_console(data)

        # {nvr_id}:browse:all|{camera_id}
        camera_id = parts.pop(0)
        if len(parts) == 0:
            return await self._build_camera(data, camera_id, build_children=True)

        # {nvr_id}:browse:all|{camera_id}:all|{event_type}
        try:
            event_type = SimpleEventType(parts.pop(0).lower())
        except (IndexError, ValueError) as err:
            return _bad_identifier(item.identifier, err)

        if len(parts) == 0:
            return await self._build_events_type(
                data, camera_id, event_type, build_children=True
            )

        try:
            time_type = IdentifierTimeType(parts.pop(0))
        except ValueError as err:
            return _bad_identifier(item.identifier, err)

        if len(parts) == 0:
            return _bad_identifier(item.identifier)

        # {nvr_id}:browse:all|{camera_id}:all|{event_type}:recent:{day_count}
        if time_type == IdentifierTimeType.RECENT:
            try:
                days = int(parts.pop(0))
            except (IndexError, ValueError) as err:
                return _bad_identifier(item.identifier, err)

            return await self._build_recent(
                data, camera_id, event_type, days, build_children=True
            )

        # {nvr_id}:all|{camera_id}:all|{event_type}:range:{year}:{month}
        # {nvr_id}:all|{camera_id}:all|{event_type}:range:{year}:{month}:all|{day}
        try:
            start, is_month, is_all = self._parse_range(parts)
        except (IndexError, ValueError) as err:
            return _bad_identifier(item.identifier, err)

        if is_month:
            return await self._build_month(
                data, camera_id, event_type, start, build_children=True
            )
        return await self._build_days(
            data, camera_id, event_type, start, build_children=True, is_all=is_all
        )

    def _parse_range(self, parts: list[str]) -> tuple[date, bool, bool]:
        day = 1
        is_month = True
        is_all = True
        year = int(parts[0])
        month = int(parts[1])
        if len(parts) == 3:
            is_month = False
            if parts[2] != "all":
                is_all = False
                day = int(parts[2])

        start = date(year=year, month=month, day=day)
        return start, is_month, is_all

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

    @callback
    def async_get_registry(self) -> er.EntityRegistry:
        """Get or return Entity Registry."""
        if self._registry is None:
            self._registry = er.async_get(self.hass)
        return self._registry

    def _breadcrumb(
        self,
        data: ProtectData,
        base_title: str,
        camera: Camera | None = None,
        event_type: SimpleEventType | None = None,
        count: int | None = None,
    ) -> str:
        title = base_title
        if count is not None:
            if count == data.max_events:
                title = f"{title} ({count} TRUNCATED)"
            else:
                title = f"{title} ({count})"

        if event_type is not None:
            title = f"{EVENT_NAME_MAP[event_type].title()} > {title}"

        if camera is not None:
            title = f"{camera.display_name} > {title}"
        title = f"{data.api.bootstrap.nvr.display_name} > {title}"

        return title

    async def _build_event(
        self,
        data: ProtectData,
        event: dict[str, Any] | Event,
        thumbnail_only: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for an individual event."""

        if isinstance(event, Event):
            event_id = event.id
            event_type = event.type
            start = event.start
            end = event.end
        else:
            event_id = event["id"]
            event_type = event["type"]
            start = from_js_time(event["start"])
            end = from_js_time(event["end"])

        assert end is not None

        title = dt_util.as_local(start).strftime("%x %X")
        duration = end - start
        title += f" {_format_duration(duration)}"
        if event_type == EventType.RING.value:
            event_text = "Ring Event"
        elif event_type == EventType.MOTION.value:
            event_text = "Motion Event"
        elif event_type == EventType.SMART_DETECT.value:
            if isinstance(event, Event):
                smart_type = event.smart_detect_types[0]
            else:
                smart_type = SmartDetectObjectType(event["smartDetectTypes"][0])
            event_text = f"Smart Detection - {smart_type.name.title()}"
        title += f" {event_text}"

        nvr = data.api.bootstrap.nvr
        if thumbnail_only:
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{nvr.id}:eventthumb:{event_id}",
                media_class=MediaClass.IMAGE,
                media_content_type="image/jpeg",
                title=title,
                can_play=True,
                can_expand=False,
                thumbnail=async_generate_thumbnail_url(
                    event_id, nvr.id, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT
                ),
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{nvr.id}:event:{event_id}",
            media_class=MediaClass.VIDEO,
            media_content_type="video/mp4",
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=async_generate_thumbnail_url(
                event_id, nvr.id, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT
            ),
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
        """Build media source for a given range of time and event type."""

        if event_type is None:
            types = [
                EventType.RING,
                EventType.MOTION,
                EventType.SMART_DETECT,
            ]
        else:
            types = [event_type]

        sources: list[BrowseMediaSource] = []
        events = await data.api.get_events_raw(
            start=start, end=end, types=types, limit=data.max_events
        )
        events = sorted(events, key=lambda e: cast(int, e["start"]), reverse=reserve)
        for event in events:
            # do not process ongoing events
            if event.get("start") is None or event.get("end") is None:
                continue

            if camera_id is not None and event.get("camera") != camera_id:
                continue

            # smart detect events have a paired motion event
            if event.get("type") == EventType.MOTION.value and event.get(
                "smartDetectEvents"
            ):
                continue

            sources.append(await self._build_event(data, event))

        return sources

    async def _build_recent(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        days: int,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for events in relative days."""

        base_id = f"{data.api.bootstrap.nvr.id}:browse:{camera_id}:{event_type.value}"
        title = f"Last {days} Days"
        if days == 1:
            title = "Last 24 Hours"

        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{base_id}:recent:{days}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="video/mp4",
            title=title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
        )

        if not build_children:
            return source

        now = dt_util.now()

        args = {
            "data": data,
            "start": now - timedelta(days=days),
            "end": now,
            "reserve": True,
        }
        if event_type != SimpleEventType.ALL:
            args["event_type"] = get_ufp_event(event_type)

        camera: Camera | None = None
        if camera_id != "all":
            camera = data.api.bootstrap.cameras.get(camera_id)
            args["camera_id"] = camera_id

        events = await self._build_events(**args)  # type: ignore[arg-type]
        source.children = events
        source.title = self._breadcrumb(
            data,
            title,
            camera=camera,
            event_type=event_type,
            count=len(events),
        )
        return source

    async def _build_month(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        start: date,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for selectors for a given month."""

        base_id = f"{data.api.bootstrap.nvr.id}:browse:{camera_id}:{event_type.value}"

        title = f"{start.strftime('%B %Y')}"
        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{base_id}:range:{start.year}:{start.month}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
        )

        if not build_children:
            return source

        if data.api.bootstrap.recording_start is not None:
            recording_start = data.api.bootstrap.recording_start.date()
        start = max(recording_start, start)

        recording_end = dt_util.now().date()
        end = start.replace(month=start.month + 1) - timedelta(days=1)
        end = min(recording_end, end)

        children = [self._build_days(data, camera_id, event_type, start, is_all=True)]
        while start <= end:
            children.append(
                self._build_days(data, camera_id, event_type, start, is_all=False)
            )
            start = start + timedelta(hours=24)

        camera: Camera | None = None
        if camera_id != "all":
            camera = data.api.bootstrap.cameras.get(camera_id)

        source.children = await asyncio.gather(*children)
        source.title = self._breadcrumb(
            data,
            title,
            camera=camera,
            event_type=event_type,
        )

        return source

    async def _build_days(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        start: date,
        is_all: bool = True,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build media source for events for a given day or whole month."""

        base_id = f"{data.api.bootstrap.nvr.id}:browse:{camera_id}:{event_type.value}"

        if is_all:
            title = "Whole Month"
            identifier = f"{base_id}:range:{start.year}:{start.month}:all"
        else:
            title = f"{start.strftime('%x')}"
            identifier = f"{base_id}:range:{start.year}:{start.month}:{start.day}"
        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
        )

        if not build_children:
            return source

        start_dt = datetime(
            year=start.year,
            month=start.month,
            day=start.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=dt_util.DEFAULT_TIME_ZONE,
        )
        if is_all:
            if start_dt.month < 12:
                end_dt = start_dt.replace(month=start_dt.month + 1)
            else:
                end_dt = start_dt.replace(year=start_dt.year + 1, month=1)
        else:
            end_dt = start_dt + timedelta(hours=24)

        args = {
            "data": data,
            "start": start_dt,
            "end": end_dt,
            "reserve": False,
        }
        if event_type != SimpleEventType.ALL:
            args["event_type"] = get_ufp_event(event_type)

        camera: Camera | None = None
        if camera_id != "all":
            camera = data.api.bootstrap.cameras.get(camera_id)
            args["camera_id"] = camera_id

        title = f"{start.strftime('%B %Y')} > {title}"
        events = await self._build_events(**args)  # type: ignore[arg-type]
        source.children = events
        source.title = self._breadcrumb(
            data,
            title,
            camera=camera,
            event_type=event_type,
            count=len(events),
        )

        return source

    async def _build_events_type(
        self,
        data: ProtectData,
        camera_id: str,
        event_type: SimpleEventType,
        build_children: bool = False,
    ) -> BrowseMediaSource:
        """Build folder media source for a selectors for a given event type."""

        base_id = f"{data.api.bootstrap.nvr.id}:browse:{camera_id}:{event_type.value}"

        title = EVENT_NAME_MAP[event_type].title()
        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=base_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
        )

        if not build_children or data.api.bootstrap.recording_start is None:
            return source

        children = [
            self._build_recent(data, camera_id, event_type, 1),
            self._build_recent(data, camera_id, event_type, 7),
            self._build_recent(data, camera_id, event_type, 30),
        ]

        start, end = _get_month_start_end(data.api.bootstrap.recording_start)
        while end > start:
            children.append(self._build_month(data, camera_id, event_type, end.date()))
            end = (end - timedelta(days=1)).replace(day=1)

        camera: Camera | None = None
        if camera_id != "all":
            camera = data.api.bootstrap.cameras.get(camera_id)
        source.children = await asyncio.gather(*children)
        source.title = self._breadcrumb(data, title, camera=camera)

        return source

    async def _get_camera_thumbnail_url(self, camera: Camera) -> str | None:
        """Get camera thumbnail URL using the first available camera entity."""

        if not camera.is_connected or camera.is_privacy_on:
            return None

        entity_id: str | None = None
        entity_registry = self.async_get_registry()
        for channel in camera.channels:
            # do not use the package camera
            if channel.id == 3:
                continue

            base_id = f"{camera.mac}_{channel.id}"
            entity_id = entity_registry.async_get_entity_id(
                Platform.CAMERA, DOMAIN, base_id
            )
            if entity_id is None:
                entity_id = entity_registry.async_get_entity_id(
                    Platform.CAMERA, DOMAIN, f"{base_id}_insecure"
                )

            if entity_id:
                # verify entity is available
                entry = entity_registry.async_get(entity_id)
                if entry and not entry.disabled:
                    break
                entity_id = None

        if entity_id is not None:
            url = URL(CameraImageView.url.format(entity_id=entity_id))
            return str(
                url.update_query({"width": THUMBNAIL_WIDTH, "height": THUMBNAIL_HEIGHT})
            )
        return None

    async def _build_camera(
        self, data: ProtectData, camera_id: str, build_children: bool = False
    ) -> BrowseMediaSource:
        """Build media source for selectors for a UniFi Protect camera."""

        name = "All Cameras"
        is_doorbell = data.api.bootstrap.has_doorbell
        has_smart = data.api.bootstrap.has_smart_detections
        camera: Camera | None = None
        if camera_id != "all":
            camera = data.api.bootstrap.cameras.get(camera_id)
            if camera is None:
                raise BrowseError(f"Unknown Camera ID: {camera_id}")
            name = camera.name or camera.market_name or camera.type
            is_doorbell = camera.feature_flags.has_chime
            has_smart = camera.feature_flags.has_smart_detect

        thumbnail_url: str | None = None
        if camera is not None:
            thumbnail_url = await self._get_camera_thumbnail_url(camera)
        source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{data.api.bootstrap.nvr.id}:browse:{camera_id}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=name,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
            children_media_class=MediaClass.VIDEO,
        )

        if not build_children:
            return source

        source.children = [
            await self._build_events_type(data, camera_id, SimpleEventType.MOTION),
        ]

        if is_doorbell:
            source.children.insert(
                0,
                await self._build_events_type(data, camera_id, SimpleEventType.RING),
            )

        if has_smart:
            source.children.append(
                await self._build_events_type(data, camera_id, SimpleEventType.SMART)
            )

        if is_doorbell or has_smart:
            source.children.insert(
                0,
                await self._build_events_type(data, camera_id, SimpleEventType.ALL),
            )

        source.title = self._breadcrumb(data, name)

        return source

    async def _build_cameras(self, data: ProtectData) -> list[BrowseMediaSource]:
        """Build media source for a single UniFi Protect NVR."""

        cameras: list[BrowseMediaSource] = [await self._build_camera(data, "all")]

        for camera in data.get_by_types({ModelType.CAMERA}):
            camera = cast(Camera, camera)
            if not camera.can_read_media(data.api.bootstrap.auth_user):
                continue
            cameras.append(await self._build_camera(data, camera.id))

        return cameras

    async def _build_console(self, data: ProtectData) -> BrowseMediaSource:
        """Build media source for a single UniFi Protect NVR."""

        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{data.api.bootstrap.nvr.id}:browse",
            media_class=MediaClass.DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=data.api.bootstrap.nvr.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
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
            consoles.append(console_source)

        if len(consoles) == 1:
            return consoles[0]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=VIDEO_FORMAT,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
            children=consoles,
        )
