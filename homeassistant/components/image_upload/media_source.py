"""Expose image_upload as media sources."""

from __future__ import annotations

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_media_source(hass: HomeAssistant) -> ImageUploadMediaSource:
    """Set up image media source."""
    return ImageUploadMediaSource(hass)


class ImageUploadMediaSource(MediaSource):
    """Provide images as media sources."""

    name: str = "Image Upload"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ImageMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        image = self.hass.data[DOMAIN].data.get(item.identifier)

        if not image:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        return PlayMedia(
            f"/api/image/serve/{image['id']}/original", image["content_type"]
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            raise BrowseError("Unknown item")

        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=image["id"],
                media_class=MediaClass.IMAGE,
                media_content_type=image["content_type"],
                title=image["name"],
                thumbnail=f"/api/image/serve/{image['id']}/256x256",
                can_play=True,
                can_expand=False,
            )
            for image in self.hass.data[DOMAIN].data.values()
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Image Upload",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
            children=children,
        )
