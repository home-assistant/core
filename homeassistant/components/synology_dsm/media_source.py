"""Expose Radio Browser as a media source."""
from __future__ import annotations

import asyncio

# import base64
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
        return self.hass.data.get(DOMAIN)  # [self.entry.unique_id]

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        diskstation = self.diskstation

        if diskstation is None:
            raise Unresolvable("Diskstation not initialized")

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
        # await self._async_generate_thumbnail(items[0], diskstation)

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f'{item.identifier}:{items_item["additional"]["thumbnail"]["cache_key"]}:{items_item["filename"]}',
                media_class=MEDIA_CLASS_IMAGE,
                media_content_type="image/jpeg",
                title=items_item["filename"],
                can_play=False,
                can_expand=False,
                # thumbnail=self._async_generate_thumbnail(items_item, diskstation),
            )
            for items_item in items
        ]

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        parts = item.identifier.split(":")
        cache_key = parts[1]
        # image_id = cache_key.split("_")[0]
        # api = self.diskstation.api
        # loop = asyncio.get_event_loop()
        # thumbnail = await loop.run_in_executor(
        #    None, api.photos.get_thumbnail, image_id, cache_key
        # )
        mime_type, _ = mimetypes.guess_type(parts[2])
        # base64_data = base64.b64encode(thumbnail)
        assert isinstance(mime_type, str)
        return PlayMedia(f"data:image/jpeg;base64, {cache_key}", mime_type)
