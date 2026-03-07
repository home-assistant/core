"""Media source for Nest Legacy camera events."""

from __future__ import annotations

from collections import defaultdict
import datetime
import logging
from typing import cast

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import NestConfigEntry
from .pynest.exceptions import PynestException
from .pynest.models import NestCamera

_LOGGER = logging.getLogger(__name__)

# URL format for playable clips
_MEDIA_CLIP_URL_FORMAT = (
    "/api/nest_legacy/event_media/{config_entry_id}/{serial_number}/{event_id}/clip"
)
_CLIP_VIEW_NAME = "api:nest_legacy:event_media:clip"

# URL format for thumbnails
_MEDIA_THUMBNAIL_URL_FORMAT = "/api/nest_legacy/event_media/{config_entry_id}/{serial_number}/{event_id}/thumbnail"
_THUMBNAIL_VIEW_NAME = "api:nest_legacy:event_media:thumbnail"

# Number of days back to display in the media browser
_DAYS_LOOKBACK = 10
# Number of events to show per page
_EVENTS_PER_PAGE = 20


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Nest media source."""
    hass.http.register_view(NestEventClipView(hass))
    hass.http.register_view(NestEventThumbnailView(hass))
    return NestMediaSource(hass)


class NestEventMediaView(HomeAssistantView):
    """Base class for Nest media views."""

    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass

    async def _handle_request(
        self,
        request: web.Request,
        config_entry_id: str,
        serial_number: str,
    ) -> tuple[NestConfigEntry, NestCamera]:
        """Handle the media request."""
        entry = self.hass.config_entries.async_get_entry(config_entry_id)
        if not entry:
            raise web.HTTPNotFound

        coordinator = cast(NestConfigEntry, entry).runtime_data
        device = coordinator.data.get(serial_number)
        if not isinstance(device, NestCamera):
            raise web.HTTPNotFound

        return cast(NestConfigEntry, entry), device


class NestEventClipView(NestEventMediaView):
    """Provide a view to serve Nest event clips."""

    url = _MEDIA_CLIP_URL_FORMAT
    name = _CLIP_VIEW_NAME

    async def get(
        self,
        request: web.Request,
        config_entry_id: str,
        serial_number: str,
        event_id: str,
    ) -> web.StreamResponse:
        """Serve a Nest event clip."""
        entry, device = await self._handle_request(
            request, config_entry_id, serial_number
        )
        coordinator = entry.runtime_data
        try:
            async with coordinator.client.async_get_camera_event_media_stream(
                device, event_id, format="mp4"
            ) as response:
                if not response:
                    raise web.HTTPNotFound

                stream = web.StreamResponse()
                stream.content_type = "video/mp4"
                await stream.prepare(request)

                async for chunk in response.content.iter_chunked(4096):
                    await stream.write(chunk)

                return stream
        except PynestException as err:
            _LOGGER.error("Error fetching event media clip: %r", err)
            raise web.HTTPInternalServerError from err


class NestEventThumbnailView(NestEventMediaView):
    """Provide a view to serve Nest event thumbnails."""

    url = _MEDIA_THUMBNAIL_URL_FORMAT
    name = _THUMBNAIL_VIEW_NAME

    async def get(
        self,
        request: web.Request,
        config_entry_id: str,
        serial_number: str,
        event_id: str,
    ) -> web.Response:
        """Serve a Nest event thumbnail."""
        entry, device = await self._handle_request(
            request, config_entry_id, serial_number
        )
        coordinator = entry.runtime_data
        try:
            async with coordinator.client.async_get_camera_event_media_stream(
                device, event_id, height=92, format="jpeg"
            ) as response:
                if not response:
                    raise web.HTTPNotFound

                image_bytes = await response.read()
                return web.Response(body=image_bytes, content_type="image/jpeg")
        except PynestException as err:
            _LOGGER.error("Error fetching event media thumbnail: %r", err)
            raise web.HTTPInternalServerError from err


class NestMediaSource(MediaSource):
    """Provide Nest camera event snapshots as a media source."""

    name: str = "Nest Legacy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize NestMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _get_config_entry(self, config_entry_id: str) -> NestConfigEntry:
        """Return the config entry."""
        entry = self.hass.config_entries.async_get_entry(config_entry_id)
        if not entry:
            raise Unresolvable(f"Config entry not found: {config_entry_id}")
        return cast(NestConfigEntry, entry)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a URL."""
        parts = item.identifier.split("/")
        if len(parts) != 3:  # config_entry_id/serial_number/event_id
            raise Unresolvable(
                f"Invalid media identifier for resolving: {item.identifier}"
            )

        config_entry_id, serial_number, event_id = parts
        url = _MEDIA_CLIP_URL_FORMAT.format(
            config_entry_id=config_entry_id,
            serial_number=serial_number,
            event_id=event_id,
        )
        return PlayMedia(url, "video/mp4")

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media browser."""
        if not item.identifier:
            entries = self.hass.config_entries.async_loaded_entries(DOMAIN)
            if len(entries) == 1:
                return await self._browse_cameras(entries[0])
            return self._browse_root(entries)

        parts = item.identifier.split("/")
        config_entry_id = parts[0]
        entry = self._get_config_entry(config_entry_id)

        if len(parts) == 1:
            return await self._browse_cameras(entry)
        if len(parts) == 2:
            return self._browse_days_for_camera(entry, parts[1])
        if len(parts) == 3:
            return await self._browse_event_types_for_day(entry, parts[1], parts[2])
        if len(parts) >= 4:
            page = int(parts[4]) if len(parts) > 4 else 0
            return await self._browse_events_paginated(
                entry, parts[1], parts[2], parts[3], page
            )

        raise BrowseError(f"Invalid media identifier path: {item.identifier}")

    def _browse_root(self, entries: list[NestConfigEntry]) -> BrowseMediaSource:
        """Browse all available config entries."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry.entry_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=entry.title,
                    can_play=False,
                    can_expand=True,
                )
                for entry in entries
            ],
        )

    async def _browse_cameras(self, entry: NestConfigEntry) -> BrowseMediaSource:
        """Browse all available cameras for a config entry."""
        coordinator = entry.runtime_data
        entity_registry = er.async_get(self.hass)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry.entry_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title="Cameras",
            can_play=False,
            can_expand=True,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}/{device.serial_number}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=f"{device.location} {device.name}".strip(),
                    can_play=False,
                    can_expand=True,
                    thumbnail=(
                        f"/api/camera_proxy/{entity}"
                        if (
                            entity := entity_registry.async_get_entity_id(
                                "camera", DOMAIN, device.serial_number
                            )
                        )
                        else None
                    ),
                )
                for device in coordinator.data.values()
                if isinstance(device, NestCamera) and device.online
            ],
        )

    def _browse_days_for_camera(
        self, entry: NestConfigEntry, serial_number: str
    ) -> BrowseMediaSource:
        """Browse day directories for a specific camera."""
        coordinator = entry.runtime_data
        device = coordinator.data.get(serial_number)
        if not isinstance(device, NestCamera):
            raise Unresolvable(f"Device not found: {serial_number}")

        today = dt_util.now().date()
        children = []
        for i in range(_DAYS_LOOKBACK):
            day = today - datetime.timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")

            if i == 0:
                title = "Today"
            elif i == 1:
                title = "Yesterday"
            else:
                title = day.strftime("%A, %B %d")

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}/{serial_number}/{day_str}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=title,
                    can_play=False,
                    can_expand=True,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}/{serial_number}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=f"Recent Days for {device.location} {device.name}".strip(),
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_event_types_for_day(
        self, entry: NestConfigEntry, serial_number: str, day_str: str
    ) -> BrowseMediaSource:
        """Browse event type directories for a specific day."""
        coordinator = entry.runtime_data
        device = coordinator.data.get(serial_number)
        if not isinstance(device, NestCamera):
            raise Unresolvable(f"Device not found: {serial_number}")

        day_dt = datetime.datetime.strptime(day_str, "%Y-%m-%d").date()
        start_of_day = dt_util.start_of_local_day(
            datetime.datetime.combine(day_dt, datetime.time.min)
        )
        end_of_day = start_of_day + datetime.timedelta(days=1)

        try:
            events = await coordinator.client.async_get_camera_events(
                device,
                start_time=int(start_of_day.timestamp()),
                end_time=int(end_of_day.timestamp()),
            )
        except PynestException as err:
            raise Unresolvable(f"Error fetching events: {err}") from err

        event_counts: dict[str, int] = defaultdict(int)
        for event in events:
            for event_type in event.get("types", []):
                event_counts[event_type] += 1

        children = []
        if events:
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}/{serial_number}/{day_str}/all",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=f"All Events ({len(events)})",
                    can_play=False,
                    can_expand=True,
                )
            )
        for event_type, count in sorted(event_counts.items()):
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}/{serial_number}/{day_str}/{event_type}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=f"{event_type.replace('-', ' ').capitalize()} Events ({count})",
                    can_play=False,
                    can_expand=True,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}/{serial_number}/{day_str}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=f"Events for {day_str}",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_events_paginated(
        self,
        entry: NestConfigEntry,
        serial_number: str,
        day_str: str,
        browse_event_type: str,
        page: int,
    ) -> BrowseMediaSource:
        """Browse a paginated list of events."""
        coordinator = entry.runtime_data
        device = coordinator.data.get(serial_number)
        if not isinstance(device, NestCamera):
            raise Unresolvable(f"Device not found: {serial_number}")

        day_dt = datetime.datetime.strptime(day_str, "%Y-%m-%d").date()
        start_of_day = dt_util.start_of_local_day(
            datetime.datetime.combine(day_dt, datetime.time.min)
        )
        end_of_day = start_of_day + datetime.timedelta(days=1)

        types_to_fetch = [browse_event_type] if browse_event_type != "all" else None
        try:
            all_events = await coordinator.client.async_get_camera_events(
                device,
                start_time=int(start_of_day.timestamp()),
                end_time=int(end_of_day.timestamp()),
                types=types_to_fetch,
            )
        except PynestException as err:
            raise Unresolvable(f"Error fetching events: {err}") from err

        sorted_events = sorted(
            all_events, key=lambda e: e.get("start_time", 0), reverse=True
        )

        start_index = page * _EVENTS_PER_PAGE
        end_index = start_index + _EVENTS_PER_PAGE
        page_events = sorted_events[start_index:end_index]

        children = []
        for event in page_events:
            event_id = event.get("id")
            if not event_id:
                continue

            start_time = event.get("start_time", 0)
            if start_time > 1e10:
                start_time /= 1000
            dt_object = dt_util.as_local(dt_util.utc_from_timestamp(start_time))
            display_type = ", ".join(event.get("types", [])).capitalize()
            title = f"{display_type} at {dt_object.strftime('%H:%M:%S')}"

            # Resolvable identifier
            media_identifier = f"{entry.entry_id}/{serial_number}/{event_id}"

            thumbnail_url = _MEDIA_THUMBNAIL_URL_FORMAT.format(
                config_entry_id=entry.entry_id,
                serial_number=serial_number,
                event_id=event_id,
            )

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=media_identifier,
                    media_class=MediaClass.VIDEO,
                    media_content_type="video/mp4",
                    title=title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=thumbnail_url,
                )
            )

        # Add "Next Page" button if there are more events
        if len(sorted_events) > end_index:
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}/{serial_number}/{day_str}/{browse_event_type}/{page + 1}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=f"Next Page ({end_index + 1} - {min(end_index + _EVENTS_PER_PAGE, len(sorted_events))})",
                    can_play=False,
                    can_expand=True,
                )
            )

        title_event_type = browse_event_type.replace("-", " ").capitalize()
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}/{serial_number}/{day_str}/{browse_event_type}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=f"{title_event_type} Events",
            can_play=False,
            can_expand=True,
            children=children,
        )
