"""Expose Radio Browser as a media source."""
from __future__ import annotations

import asyncio
import base64
import mimetypes

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
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import SynologyDSMData


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Synology media source."""
    # Synology photos support only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return SynologyPhotosMediaSource(hass, entry)


class SynologyPhotosMediaSource(MediaSource):
    """Provide Synology Photos as media sources."""

    name = "Synology Photos"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Synology source."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

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
        diskstation: SynologyDSMData = self.hass.data[DOMAIN][self.entry.unique_id]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_IMAGE,
            media_content_type=MEDIA_TYPE_IMAGE,
            title="Synology Photos",
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
            children=[
                *await self._async_build_albums(diskstation, item),
            ],
        )

    async def _async_build_albums(
        self, diskstation: SynologyDSMData, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing Albums."""
        api = diskstation.api

        if not item.identifier:
            # Get Albums
            # The library works sync, and this expects async calls
            loop = asyncio.get_event_loop()
            albums = await loop.run_in_executor(None, api.photos.get_albums)
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f'{album["id"]}',
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_type=MEDIA_TYPE_IMAGE,
                    title=album["name"],
                    can_play=False,
                    can_expand=True,
                )
                for album in albums
            ]

        # Request items of album
        # Get Items
        # The library works sync, and this expects async calls
        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(
            None, api.photos.get_items, item.identifier, 0, 1000, '["thumbnail"]'
        )
        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f'{item.identifier}:{items_item["additional"]["thumbnail"]["cache_key"]}:{items_item["filename"]}',
                media_class=MEDIA_CLASS_IMAGE,
                media_content_type="image/jpeg",
                title=items_item["filename"],
                can_play=False,
                can_expand=False,
                # thumbnail can't be base64 encoded. It needs to be an url
                # thumbnail=await self.async_get_thumbnail(
                #    items_item["additional"]["thumbnail"]["cache_key"],
                #    items_item["id"],
                #    "sm",
                # ),
            )
            for items_item in items
        ]

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        parts = item.identifier.split(":")
        cache_key = parts[1]
        image_id = cache_key.split("_")[0]
        mime_type, _ = mimetypes.guess_type(parts[2])
        assert isinstance(mime_type, str)
        image = await self.async_get_thumbnail(cache_key, image_id, "xl", mime_type)
        return PlayMedia(image, mime_type)

    async def async_get_thumbnail(
        self, cache_key: str, image_id: str, size: str, mime_type: str
    ) -> str:
        """Get thumbnail in base64."""
        # diskstation = self.diskstation
        if not self.hass.data.get(DOMAIN):
            raise Unresolvable("Diskstation not initialized")

        diskstation: SynologyDSMData = self.hass.data[DOMAIN][self.entry.unique_id]
        loop = asyncio.get_event_loop()
        thumbnail = await loop.run_in_executor(
            None, diskstation.api.photos.get_thumbnail, image_id, cache_key, size
        )
        base64_data = base64.b64encode(thumbnail)
        return f"data:{mime_type};base64, {base64_data.decode()}"
