"""Expose Synology DSM as a media source."""
from __future__ import annotations

import mimetypes
from pathlib import Path
import tempfile

from aiohttp import web
from synology_dsm.api.photos import SynoPhotosAlbum, SynoPhotosItem
from synology_dsm.exceptions import SynologyDSMException

from homeassistant.components import http
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import SynologyDSMData


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Synology media source."""
    # Synology photos support only a single config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    hass.http.register_view(SynologyDsmMediaView(hass))
    return SynologyPhotosMediaSource(hass, entries)


class SynologyPhotosMediaSource(MediaSource):
    """Provide Synology Photos as media sources."""

    name = "Synology Photos"

    def __init__(self, hass: HomeAssistant, entries: list[ConfigEntry]) -> None:
        """Initialize Synology source."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entries = entries

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
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaClass.IMAGE,
            title="Synology Photos",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
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
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaClass.IMAGE,
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
            try:
                albums = await diskstation.api.photos.get_albums()
            except SynologyDSMException:
                return []

            ret = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{item.identifier}/0",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title="All images",
                    can_play=False,
                    can_expand=True,
                )
            ]
            for album in albums:
                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{item.identifier}/{album.album_id}",
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaClass.IMAGE,
                        title=album.name,
                        can_play=False,
                        can_expand=True,
                    )
                )

            return ret

        # Request items of album
        # Get Items
        album = SynoPhotosAlbum(int(identifier_parts[1]), "", 0)
        try:
            album_items = await diskstation.api.photos.get_items_from_album(
                album, 0, 1000
            )
        except SynologyDSMException:
            return []

        ret = []
        for items_item in album_items:
            mime_type, _ = mimetypes.guess_type(items_item.file_name)
            assert isinstance(mime_type, str)
            if mime_type.startswith("image/"):
                # Force small small thumbnails
                items_item.thumbnail_size = "sm"
                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{identifier_parts[0]}/{identifier_parts[1]}/{items_item.thumbnail_cache_key}/{items_item.file_name}",
                        media_class=MediaClass.IMAGE,
                        media_content_type=mime_type,
                        title=items_item.file_name,
                        can_play=True,
                        can_expand=False,
                        thumbnail=await self.async_get_thumbnail(
                            items_item, diskstation
                        ),
                    )
                )
        return ret

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        parts = item.identifier.split("/")
        unique_id = parts[0]
        cache_key = parts[2]
        file_name = parts[3]
        mime_type, _ = mimetypes.guess_type(parts[3])
        if not isinstance(mime_type, str):
            raise Unresolvable("No file extension")
        return PlayMedia(
            f"/synology_dsm/{unique_id}/{cache_key}/{file_name}", mime_type
        )

    async def async_get_thumbnail(
        self, item: SynoPhotosItem, diskstation: SynologyDSMData
    ) -> str:
        """Get thumbnail."""
        if not self.hass.data.get(DOMAIN):
            raise Unresolvable("Diskstation not initialized")

        try:
            thumbnail = await diskstation.api.photos.get_item_thumbnail_url(item)
        except SynologyDSMException:
            return ""
        return str(thumbnail)


class SynologyDsmMediaView(http.HomeAssistantView):
    """Synology Media Finder View."""

    url = "/synology_dsm/{source_dir_id}/{location:.*}"
    name = "synology_dsm"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass

    async def get(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> web.FileResponse:
        """Start a GET request."""
        if not self.hass.data.get(DOMAIN):
            raise web.HTTPNotFound()
        # location: {cache_key}/{filename}
        cache_key, file_name = location.split("/")
        image_id = cache_key.split("_")[0]
        file_extension = file_name.split(".")[-1]
        mime_type, _ = mimetypes.guess_type(file_name)
        if not isinstance(mime_type, str):
            raise web.HTTPNotFound()
        diskstation: SynologyDSMData = self.hass.data[DOMAIN][source_dir_id]

        item = SynoPhotosItem(image_id, "", "", "", cache_key, "")
        try:
            image = await diskstation.api.photos.download_item(item)
        except SynologyDSMException as exc:
            raise web.HTTPNotFound() from exc
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=f".{file_extension}", delete=False
        ) as temp:
            temp.write(image)
            return web.FileResponse(Path(temp.name))
