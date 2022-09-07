"""Expose Synology DSM as a media source."""
from __future__ import annotations

import mimetypes
from pathlib import Path
import tempfile

from aiohttp import web

from homeassistant.components import http
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_IMAGE,
    MEDIA_TYPE_IMAGE,
)
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .models import SynologyDSMData


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Synology media source."""
    # Synology photos support only a single config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    return SynologyPhotosMediaSource(hass, entries)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up local media source."""
    hass.http.register_view(SynologyDsmMediaView(hass))


class SynologyPhotosMediaSource(MediaSource):
    """Provide Synology Photos as media sources."""

    name = "Synology Photos"

    def __init__(self, hass: HomeAssistant, entries: list[ConfigEntry]) -> None:
        """Initialize Synology source."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entries = entries

    @property
    def diskstation(self) -> SynologyDSMData | None:
        """Return the Synology dsm."""
        return self.hass.data.get(DOMAIN)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not self.hass.data.get(DOMAIN):
            raise Unresolvable("Diskstation not initialized")
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_IMAGE,
            title="Synology Photos",
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
            children=[
                *await self._async_build_diskstations(item),
            ],
        )

    async def _async_build_diskstations(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing different diskstations."""
        ret = []

        if not item.identifier:
            for entry in self.entries:
                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=entry.unique_id,
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_type=MEDIA_TYPE_IMAGE,
                        title=f"{entry.title} - {entry.unique_id}",
                        can_play=False,
                        can_expand=True,
                    )
                )
            return ret
        identifier_parts = item.identifier.split("/")
        diskstation: SynologyDSMData = self.hass.data[DOMAIN][identifier_parts[0]]

        if len(identifier_parts) == 1:
            # Get Albums
            # The library works sync, and this expects async calls
            albums = await self.hass.loop.run_in_executor(
                None, diskstation.api.photos.get_albums
            )
            ret = []
            for album in albums:
                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f'{item.identifier}/{album["id"]}',
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_type=MEDIA_TYPE_IMAGE,
                        title=album["name"],
                        can_play=False,
                        can_expand=True,
                    )
                )

            return ret

        # Request items of album
        # Get Items
        # The library works sync, and this expects async calls
        items = await self.hass.loop.run_in_executor(
            None,
            diskstation.api.photos.get_items,
            identifier_parts[1],
            0,
            1000,
            '["thumbnail"]',
        )
        ret = []
        for items_item in items:
            mime_type, _ = mimetypes.guess_type(items_item["filename"])
            assert isinstance(mime_type, str)
            parts = mime_type.split("/")
            if parts[0] == "image":
                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f'{item.identifier}/{items_item["additional"]["thumbnail"]["cache_key"]}/{items_item["filename"]}',
                        media_class=MEDIA_CLASS_IMAGE,
                        media_content_type=mime_type,
                        title=items_item["filename"],
                        can_play=True,
                        can_expand=False,
                        thumbnail=await self.async_get_thumbnail(
                            items_item["additional"]["thumbnail"]["cache_key"],
                            items_item["id"],
                            "sm",
                            identifier_parts[0],
                        ),
                    )
                )
        return ret

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        parts = item.identifier.split("/")
        cache_key = parts[2]
        mime_type, _ = mimetypes.guess_type(parts[3])
        assert isinstance(mime_type, str)
        return PlayMedia(f"/synology_dsm/{parts[0]}/{cache_key}/{parts[3]}", mime_type)

    async def async_get_thumbnail(
        self, cache_key: str, image_id: str, size: str, diskstation_unique_id: str
    ) -> str:
        """Get thumbnail."""
        if not self.hass.data.get(DOMAIN):
            raise Unresolvable("Diskstation not initialized")

        diskstation: SynologyDSMData = self.hass.data[DOMAIN][diskstation_unique_id]
        thumbnail = await self.hass.loop.run_in_executor(
            None, diskstation.api.photos.get_thumbnail_url, image_id, cache_key, size
        )
        return str(thumbnail)


class SynologyDsmMediaView(http.HomeAssistantView):
    """Synology Media Finder View."""

    url = "/synology_dsm/{source_dir_id}/{location:.*}"
    name = "synology_dsm"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass
        self.tempfile = tempfile.NamedTemporaryFile()
        self.tempfile_in_buffer = ""

    async def get(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> web.FileResponse:
        """Start a GET request."""
        # We cache the image, so we don't need to ask for it multiple times
        full_file_path = f"{source_dir_id}/{location}"
        if full_file_path == self.tempfile_in_buffer:
            path = Path(self.tempfile.name)
            return web.FileResponse(path)

        # Close the tempfile and clear it
        self.tempfile.close()
        self.tempfile_in_buffer = ""

        parts = location.split("/")
        cache_key = parts[0]
        image_id = cache_key.split("_")[0]
        mime_type, _ = mimetypes.guess_type(parts[1])
        assert isinstance(mime_type, str)
        if not self.hass.data.get(DOMAIN):
            raise web.HTTPNotFound()

        diskstation: SynologyDSMData = self.hass.data[DOMAIN][source_dir_id]
        image = await self.hass.loop.run_in_executor(
            None, diskstation.api.photos.get_thumbnail, image_id, cache_key, "xl"
        )
        file_parts = parts[1].split(".")
        file_extension = file_parts[len(file_parts) - 1]
        self.tempfile = tempfile.NamedTemporaryFile(
            suffix=f".{file_extension}", delete=False
        )
        fname = self.tempfile.name
        self.tempfile.write(image)
        path = Path(fname)

        # Store the file currently in buffer
        self.tempfile_in_buffer = full_file_path

        return web.FileResponse(path)
