"""Expose images as media sources."""

from __future__ import annotations

from typing import cast

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, State

from .const import DATA_COMPONENT, DOMAIN


async def async_get_media_source(hass: HomeAssistant) -> ImageMediaSource:
    """Set up image media source."""
    return ImageMediaSource(hass)


class ImageMediaSource(MediaSource):
    """Provide images as media sources."""

    name: str = "Image"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ImageMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        image = self.hass.data[DATA_COMPONENT].get_entity(item.identifier)

        if not image:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        return PlayMedia(
            f"/api/image_proxy_stream/{image.entity_id}", image.content_type
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
                identifier=image.entity_id,
                media_class=MediaClass.VIDEO,
                media_content_type=image.content_type,
                title=cast(State, self.hass.states.get(image.entity_id)).attributes.get(
                    ATTR_FRIENDLY_NAME, image.name
                ),
                thumbnail=f"/api/image_proxy/{image.entity_id}",
                can_play=True,
                can_expand=False,
            )
            for image in self.hass.data[DATA_COMPONENT].entities
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Image",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
            children=children,
        )
