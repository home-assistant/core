"""Camera platform for the Bambu Lab integration."""

import logging
from typing import override

from aiobambulab import BambuLabClient, BambuLabError

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BambuLabConfigEntry
from .entity import BambuLabEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuLabConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the camera of a Bambu Lab printer."""
    client = entry.runtime_data

    if client.state.camera_stream_enabled is not None:
        async_add_entities([BambuLabStreamCamera(client)])
    elif client.supports_camera_images:
        async_add_entities([BambuLabImageCamera(client)])


class BambuLabCamera(BambuLabEntity, Camera):
    """The camera of a Bambu Lab printer."""

    _attr_translation_key = "chamber"

    def __init__(self, client: BambuLabClient) -> None:
        """Initialize the camera."""
        super().__init__(client)
        Camera.__init__(self)
        self._attr_unique_id = f"{client.serial}_chamber"


class BambuLabImageCamera(BambuLabCamera):
    """The camera of a printer that sends images."""

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the most recent image of the camera."""
        try:
            return await self._client.camera_image()
        except BambuLabError as err:
            _LOGGER.debug("Could not get an image of the camera: %s", err)
            return None


class BambuLabStreamCamera(BambuLabCamera):
    """The camera of a printer that serves a video stream."""

    _attr_supported_features = CameraEntityFeature.STREAM

    @override
    @property
    def available(self) -> bool:
        """Return whether the printer serves its video stream."""
        return super().available and self._client.camera_stream_url is not None

    @override
    @property
    def use_stream_for_stills(self) -> bool:
        """Return that images come from the video stream."""
        return True

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return an image from the video stream."""
        stream = await self.async_create_stream()
        # A stream that just started has no image yet. Wait for one, instead
        # of ending the response without an image.
        return (
            await stream.async_get_image(
                width=width, height=height, wait_for_next_keyframe=True
            )
            if stream
            else None
        )

    @override
    async def stream_source(self) -> str | None:
        """Return the address of the video stream."""
        return self._client.camera_stream_url
