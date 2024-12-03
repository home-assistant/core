"""Expose cameras as media sources."""

from __future__ import annotations

import asyncio

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.components.stream import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import Camera, _async_stream_endpoint_url
from .const import DATA_COMPONENT, DOMAIN, StreamType


async def async_get_media_source(hass: HomeAssistant) -> CameraMediaSource:
    """Set up camera media source."""
    return CameraMediaSource(hass)


def _media_source_for_camera(
    hass: HomeAssistant, camera: Camera, content_type: str
) -> BrowseMediaSource:
    camera_state = hass.states.get(camera.entity_id)
    title = camera.name
    if camera_state:
        title = camera_state.attributes.get(ATTR_FRIENDLY_NAME, camera.name)

    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=camera.entity_id,
        media_class=MediaClass.VIDEO,
        media_content_type=content_type,
        title=title,
        thumbnail=f"/api/camera_proxy/{camera.entity_id}",
        can_play=True,
        can_expand=False,
    )


class CameraMediaSource(MediaSource):
    """Provide camera feeds as media sources."""

    name: str = "Camera"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize CameraMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        component = self.hass.data[DATA_COMPONENT]
        camera = component.get_entity(item.identifier)

        if not camera:
            raise Unresolvable(f"Could not resolve media item: {item.identifier}")

        if not (stream_types := camera.camera_capabilities.frontend_stream_types):
            return PlayMedia(
                f"/api/camera_proxy_stream/{camera.entity_id}", camera.content_type
            )

        if "stream" not in self.hass.config.components:
            raise Unresolvable("Stream integration not loaded")

        try:
            url = await _async_stream_endpoint_url(self.hass, camera, HLS_PROVIDER)
        except HomeAssistantError as err:
            # Handle known error
            if StreamType.HLS not in stream_types:
                raise Unresolvable(
                    "Camera does not support MJPEG or HLS streaming."
                ) from err
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

        async def _filter_browsable_camera(camera: Camera) -> BrowseMediaSource | None:
            stream_types = camera.camera_capabilities.frontend_stream_types
            if not stream_types:
                return _media_source_for_camera(self.hass, camera, camera.content_type)
            if not can_stream_hls:
                return None

            content_type = FORMAT_CONTENT_TYPE[HLS_PROVIDER]
            if StreamType.HLS not in stream_types and not (
                await camera.stream_source()
            ):
                return None

            return _media_source_for_camera(self.hass, camera, content_type)

        component = self.hass.data[DATA_COMPONENT]
        results = await asyncio.gather(
            *(_filter_browsable_camera(camera) for camera in component.entities),
            return_exceptions=True,
        )
        children = [
            result for result in results if isinstance(result, BrowseMediaSource)
        ]
        not_shown = len(results) - len(children)
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
