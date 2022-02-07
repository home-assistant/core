"""Expose cameras as media sources."""
from __future__ import annotations

from typing import Optional, cast

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_CLASS_VIDEO,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.components.stream.const import FORMAT_CONTENT_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.network import get_url

from . import Camera, _async_stream_endpoint_url
from .const import DOMAIN, STREAM_TYPE_HLS


async def async_get_media_source(hass: HomeAssistant) -> CamereaMediaSource:
    """Set up camera media source."""
    return CamereaMediaSource(hass)


class CamereaMediaSource(MediaSource):
    """Provide camera feeds as media sources."""

    name: str = "Camera"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize CamereaMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        component: EntityComponent = self.hass.data[DOMAIN]
        camera = cast(Optional[Camera], component.get_entity(item.identifier))

        if not camera:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        fmt = "hls"
        url = await _async_stream_endpoint_url(self.hass, camera, fmt)
        return PlayMedia(f"{get_url(self.hass)}{url}", FORMAT_CONTENT_TYPE[fmt])

    @callback
    @classmethod
    def _parse_identifier(
        cls, identifier: str
    ) -> tuple[str | None, str | None, str | None, str | None]:
        base = [None] * 4
        data = identifier.split("#", 3)
        return cast(
            tuple[Optional[str], Optional[str], Optional[str], Optional[str]],
            tuple(data + base)[:4],  # type: ignore[operator]
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            raise BrowseError("Unknown item")

        # Root. List cameras.
        component: EntityComponent = self.hass.data[DOMAIN]
        children = []
        for entity in component.entities:
            entity = cast(Camera, entity)

            if entity.frontend_stream_type != STREAM_TYPE_HLS:
                continue

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entity.entity_id,
                    media_class=MEDIA_CLASS_APP,
                    media_content_type=FORMAT_CONTENT_TYPE["hls"],
                    title=entity.name,
                    thumbnail=f"/api/camera_proxy/{entity.entity_id}",
                    can_play=True,
                    can_expand=False,
                    children_media_class=MEDIA_CLASS_VIDEO,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_APP,
            media_content_type="",
            title="Camera",
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_VIDEO,
            children=children,
        )
