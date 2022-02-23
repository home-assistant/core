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
from homeassistant.components.stream.const import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent

from . import Camera, _async_stream_endpoint_url
from .const import DOMAIN, STREAM_TYPE_HLS


async def async_get_media_source(hass: HomeAssistant) -> CameraMediaSource:
    """Set up camera media source."""
    return CameraMediaSource(hass)


class CameraMediaSource(MediaSource):
    """Provide camera feeds as media sources."""

    name: str = "Camera"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize CameraMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        component: EntityComponent = self.hass.data[DOMAIN]
        camera = cast(Optional[Camera], component.get_entity(item.identifier))

        if not camera:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        if (stream_type := camera.frontend_stream_type) is None:
            return PlayMedia(
                f"/api/camera_proxy_stream/{camera.entity_id}", camera.content_type
            )

        if stream_type != STREAM_TYPE_HLS:
            raise Unresolvable("Camera does not support MJPEG or HLS streaming.")

        if "stream" not in self.hass.config.components:
            raise Unresolvable("Stream integration not loaded")

        try:
            url = await _async_stream_endpoint_url(self.hass, camera, HLS_PROVIDER)
        except HomeAssistantError as err:
            raise Unresolvable(str(err)) from err

        return PlayMedia(url, FORMAT_CONTENT_TYPE[HLS_PROVIDER])

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            raise BrowseError("Unknown item")

        supported_stream_types: list[str | None] = [None]

        if "stream" in self.hass.config.components:
            supported_stream_types.append(STREAM_TYPE_HLS)

        # Root. List cameras.
        component: EntityComponent = self.hass.data[DOMAIN]
        children = []
        for camera in component.entities:
            camera = cast(Camera, camera)
            stream_type = camera.frontend_stream_type

            if stream_type not in supported_stream_types:
                continue

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=camera.entity_id,
                    media_class=MEDIA_CLASS_VIDEO,
                    media_content_type=FORMAT_CONTENT_TYPE[HLS_PROVIDER],
                    title=camera.name,
                    thumbnail=f"/api/camera_proxy/{camera.entity_id}",
                    can_play=True,
                    can_expand=False,
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
