"""Expose images as media sources."""

from __future__ import annotations

import logging

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DATA_IMAGES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> ImageMediaSource:
    """Set up image media source."""
    _LOGGER.debug("Setting up image media source")
    return ImageMediaSource(hass)


class ImageMediaSource(MediaSource):
    """Provide images as media sources."""

    name: str = "OpenAI Images"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ImageMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        IMAGE_STORAGE = self.hass.data.setdefault(DATA_IMAGES, {})
        image = IMAGE_STORAGE.get(item.identifier)

        if image is None:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        return PlayMedia(f"/api/{DOMAIN}/images/{item.identifier}", image.mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            raise BrowseError("Unknown item")

        IMAGE_STORAGE = self.hass.data.setdefault(DATA_IMAGES, {})

        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=filename,
                media_class=MediaClass.IMAGE,
                media_content_type=image.mime_type,
                title=image.title or filename,
                thumbnail=f"/api/{DOMAIN}/thumbnails/{filename}",
                can_play=True,
                can_expand=False,
            )
            for filename, image in IMAGE_STORAGE.items()
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="OpenAI Generated Images",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
            children=children,
        )
