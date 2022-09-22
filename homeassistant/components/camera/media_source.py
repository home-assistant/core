"""Expose cameras as media sources."""
from __future__ import annotations

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.components.stream import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent

from . import Camera, _async_stream_endpoint_url
from .const import DOMAIN, StreamType


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
        component: EntityComponent[Camera] = self.hass.data[DOMAIN]
        camera = component.get_entity(item.identifier)

        if not camera:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        if (stream_type := camera.frontend_stream_type) is None:
            return PlayMedia(
                f"/api/camera_proxy_stream/{camera.entity_id}", camera.content_type
            )

        if stream_type != StreamType.HLS:
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

        can_stream_hls = "stream" in self.hass.config.components

        # Root. List cameras.
        component: EntityComponent[Camera] = self.hass.data[DOMAIN]
        children = []
        not_shown = 0
        for camera in component.entities:
            stream_type = camera.frontend_stream_type

            if stream_type is None:
                content_type = camera.content_type

            elif can_stream_hls and stream_type == StreamType.HLS:
                content_type = FORMAT_CONTENT_TYPE[HLS_PROVIDER]

            else:
                not_shown += 1
                continue

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=camera.entity_id,
                    media_class=MediaClass.VIDEO,
                    media_content_type=content_type,
                    title=camera.name,
                    thumbnail=f"/api/camera_proxy/{camera.entity_id}",
                    can_play=True,
                    can_expand=False,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Camera",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
            children=children,
            not_shown=not_shown,
        )
