"""Expose Synology DSM as a media source."""

from __future__ import annotations

import mimetypes

from aiohttp import web
from synology_dsm.api.photos import SynoPhotosAlbum, SynoPhotosItem
from synology_dsm.exceptions import SynologyDSMException

from homeassistant.components import http
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseError,
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
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    hass.http.register_view(SynologyDsmMediaView(hass))
    return SynologyPhotosMediaSource(hass, entries)


class SynologyPhotosMediaSourceIdentifier:
    """Synology Photos item identifier."""

    def __init__(self, identifier: str) -> None:
        """Split identifier into parts."""
        parts = identifier.split("/")

        self.unique_id = None
        self.album_id = None
        self.cache_key = None
        self.file_name = None

        if parts:
            self.unique_id = parts[0]
            if len(parts) > 1:
                self.album_id = parts[1]
            if len(parts) > 2:
                self.cache_key = parts[2]
            if len(parts) > 3:
                self.file_name = parts[3]


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
            raise BrowseError("Diskstation not initialized")
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
        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry.unique_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title=f"{entry.title} - {entry.unique_id}",
                    can_play=False,
                    can_expand=True,
                )
                for entry in self.entries
            ]
        identifier = SynologyPhotosMediaSourceIdentifier(item.identifier)
        diskstation: SynologyDSMData = self.hass.data[DOMAIN][identifier.unique_id]
        assert diskstation.api.photos is not None

        if identifier.album_id is None:
            # Get Albums
            try:
                albums = await diskstation.api.photos.get_albums()
            except SynologyDSMException:
                return []
            assert albums is not None

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
            ret.extend(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{item.identifier}/{album.album_id}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title=album.name,
                    can_play=False,
                    can_expand=True,
                )
                for album in albums
            )

            return ret

        # Request items of album
        # Get Items
        album = SynoPhotosAlbum(int(identifier.album_id), "", 0)
        try:
            album_items = await diskstation.api.photos.get_items_from_album(
                album, 0, 1000
            )
        except SynologyDSMException:
            return []
        assert album_items is not None

        ret = []
        for album_item in album_items:
            mime_type, _ = mimetypes.guess_type(album_item.file_name)
            if isinstance(mime_type, str) and mime_type.startswith("image/"):
                # Force small small thumbnails
                album_item.thumbnail_size = "sm"
                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{identifier.unique_id}/{identifier.album_id}/{album_item.thumbnail_cache_key}/{album_item.file_name}",
                        media_class=MediaClass.IMAGE,
                        media_content_type=mime_type,
                        title=album_item.file_name,
                        can_play=True,
                        can_expand=False,
                        thumbnail=await self.async_get_thumbnail(
                            album_item, diskstation
                        ),
                    )
                )
        return ret

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        identifier = SynologyPhotosMediaSourceIdentifier(item.identifier)
        if identifier.album_id is None:
            raise Unresolvable("No album id")
        if identifier.file_name is None:
            raise Unresolvable("No file name")
        mime_type, _ = mimetypes.guess_type(identifier.file_name)
        if not isinstance(mime_type, str):
            raise Unresolvable("No file extension")
        return PlayMedia(
            f"/synology_dsm/{identifier.unique_id}/{identifier.cache_key}/{identifier.file_name}",
            mime_type,
        )

    async def async_get_thumbnail(
        self, item: SynoPhotosItem, diskstation: SynologyDSMData
    ) -> str | None:
        """Get thumbnail."""
        assert diskstation.api.photos is not None

        try:
            thumbnail = await diskstation.api.photos.get_item_thumbnail_url(item)
        except SynologyDSMException:
            return None
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
    ) -> web.Response:
        """Start a GET request."""
        if not self.hass.data.get(DOMAIN):
            raise web.HTTPNotFound
        # location: {cache_key}/{filename}
        cache_key, file_name = location.split("/")
        image_id = int(cache_key.split("_")[0])
        mime_type, _ = mimetypes.guess_type(file_name)
        if not isinstance(mime_type, str):
            raise web.HTTPNotFound
        diskstation: SynologyDSMData = self.hass.data[DOMAIN][source_dir_id]

        assert diskstation.api.photos is not None
        item = SynoPhotosItem(image_id, "", "", "", cache_key, "", False)
        try:
            image = await diskstation.api.photos.download_item(item)
        except SynologyDSMException as exc:
            raise web.HTTPNotFound from exc
        return web.Response(body=image, content_type=mime_type)
