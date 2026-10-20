"""Taught frames as media sources, the examples given to AI Task."""

from pathlib import Path
import re
from typing import override

from aiohttp import web

from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized

from .const import DOMAIN
from .taught_frames import FRAME_ID, FRAME_MIME_TYPE, frame_path

IDENTIFIER = re.compile(r"(?P<entry_id>[^/]+)/(?P<frame_id>[^/]+)\.jpg")
FRAME_URL = f"/api/{DOMAIN}/frame/{{entry_id}}/{{frame_id}}"


async def async_get_media_source(hass: HomeAssistant) -> TaughtFramesMediaSource:
    """Set up the media source of taught frames."""
    return TaughtFramesMediaSource(hass)


async def _async_frame_path(
    hass: HomeAssistant, entry_id: str, frame_id: str
) -> Path | None:
    """Return the file of a taught frame, None when there is none."""
    if (
        FRAME_ID.fullmatch(frame_id) is None
        or (entry := hass.config_entries.async_get_entry(entry_id)) is None
        or entry.domain != DOMAIN
    ):
        return None
    path = frame_path(hass, entry_id, frame_id)
    if not await hass.async_add_executor_job(path.is_file):
        return None
    return path


class TaughtFramesMediaSource(MediaSource):
    """Resolve taught frames to their files."""

    name = "Image classification"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a taught frame to its file."""
        if (match := IDENTIFIER.fullmatch(item.identifier)) is None or (
            path := await _async_frame_path(self.hass, **match.groupdict())
        ) is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="unknown_frame",
                translation_placeholders={"identifier": item.identifier},
            )
        return PlayMedia(
            FRAME_URL.format(**match.groupdict()), FRAME_MIME_TYPE, path=path
        )

    @override
    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return an empty folder; taught frames are managed in the options."""
        if item.identifier:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="unknown_frame",
                translation_placeholders={"identifier": item.identifier},
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children=[],
        )


class TaughtFrameView(HomeAssistantView):
    """Serve taught frames to administrators."""

    url = FRAME_URL
    name = f"api:{DOMAIN}:frame"

    async def get(
        self, request: web.Request, entry_id: str, frame_id: str
    ) -> web.FileResponse:
        """Return a taught frame."""
        # Frames show camera views, which other users may not be allowed to see.
        if not request[KEY_HASS_USER].is_admin:
            raise Unauthorized
        if (
            path := await _async_frame_path(request.app[KEY_HASS], entry_id, frame_id)
        ) is None:
            raise web.HTTPNotFound
        return web.FileResponse(path, headers={"Content-Type": FRAME_MIME_TYPE})
