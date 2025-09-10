"""Expose images as media sources."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DATA_IMAGES, DOMAIN, IMAGE_EXPIRY_TIME

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> ImageMediaSource:
    """Set up image media source."""
    _LOGGER.debug("Setting up image media source")
    return ImageMediaSource(hass)


class ImageMediaSource(MediaSource):
    """Provide images as media sources."""

    name: str = "AI Generated Images"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ImageMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        image_storage = self.hass.data[DATA_IMAGES]
        image = image_storage.get(item.identifier)

        if image is None:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        return PlayMedia(
            async_sign_path(
                self.hass,
                f"/api/{DOMAIN}/images/{item.identifier}",
                timedelta(seconds=IMAGE_EXPIRY_TIME or 1800),
            ),
            image.mime_type,
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            raise BrowseError("Unknown item")

        image_storage = self.hass.data[DATA_IMAGES]

        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=filename,
                media_class=MediaClass.IMAGE,
                media_content_type=image.mime_type,
                title=image.title or filename,
                can_play=True,
                can_expand=False,
            )
            for filename, image in image_storage.items()
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="AI Generated Images",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
            children=children,
        )
