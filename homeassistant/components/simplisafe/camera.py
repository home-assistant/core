"""Support for SimpliSafe binary sensors."""
from __future__ import annotations

from datetime import datetime
import os
from typing import Any

from simplipy.device import DeviceTypes
from simplipy.device.camera import Camera, CameraTypes
from simplipy.errors import SimplipyError
from simplipy.system.v3 import SystemV3
from simplipy.websocket import EVENT_CAMERA_MOTION_DETECTED, WebsocketEvent

import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN, LOGGER

DEFAULT_IMAGE_WIDTH = 720

# The Outdoor Camera has a custom service for saving the motion clip.
ATTR_FILENAME = "filename"
ATTR_WIDTH = "width"

SERVICE_OC_IMAGE = "capture_motion_image"
SERVICE_OC_CLIP = "capture_motion_clip"

SERVICE_OC_IMAGE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_FILENAME): cv.template,
        vol.Optional(ATTR_WIDTH, default=720): vol.Coerce(int)
    }
)

SERVICE_OC_CLIP_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_FILENAME): cv.template
    }
)

SERVICES = (
    SERVICE_OC_IMAGE,
    SERVICE_OC_CLIP,
)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe cameras based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]

    cameras: list[
        SimplisafeOutdoorCamera
    ] = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping camera setup for V2 system: %s", system.system_id)
            continue

        for camera in system.cameras.values():
            if camera.camera_type == CameraTypes.OUTDOOR_CAMERA:
                cameras.append(
                    SimplisafeOutdoorCamera(
                        hass,
                        simplisafe,
                        system,
                        camera,
                    )
                )

    async_add_entities(cameras)

class SimplisafeOutdoorCamera(SimpliSafeEntity, Camera):
    """Define the outdoor camera."""
    _device: Camera
    _attr_image_last_updated: datetime | None = None
    _attr_image_url: str | None = None
    _attr_clip_url: str | None = None
    _attr_hls_url: str | None = None
    _attr_cached_image: bytes | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        simplisafe: SimpliSafe,
        system: SystemV3,
        camera: Camera,
    ) -> None:
        """Initialize."""
        SimpliSafeEntity.__init__(
            self,
            simplisafe,
            system,
            device=camera,
            additional_websocket_events=[EVENT_CAMERA_MOTION_DETECTED],
        )
        Camera.__init__(self)

        self._hass = hass
        self._register_services()

    @property
    def name(self) -> str | None:
        """Return a good name for this camera."""
        return self._device.name

    @callback
    def async_unload(self) -> None:
        """Release resources."""
        for service in SERVICES:
            self._hass.services.async_remove(DOMAIN, service)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        if self._attr_cached_image is not None:
            return self._attr_cached_image

        if self._attr_image_url is None:
            return

        self._attr_cached_image = await self._simplisafe.async_media_request(
            self._attr_image_url.replace("{&width}", "&width=" + str(width))
        )
        return self._attr_cached_image

    def _register_services(self) -> None:
        """Register the Outdoor Camera hass service calls."""

        def _write_image(to_file: str, image_data: bytes) -> None:
            """Executor helper to write image."""
            os.makedirs(os.path.dirname(to_file), exist_ok=True)
            with open(to_file, "wb") as img_file:
                img_file.write(image_data)

        async def save_image_handler(call: ServiceCall) -> None:
            if self._attr_image_url is None:
                return

            width = call.data.get(ATTR_WIDTH)
            filename: Template = call.data.get(ATTR_FILENAME)
            filename.hass = self._hass
            snapshot_file = filename.async_render(variables={ATTR_ENTITY_ID: self})

            try:
                snapshot = await self._simplisafe.async_media_request(
                    self._attr_image_url.replace("{&width}", "&width=" + str(width))
                )
            except SimplipyError as err:
                raise HomeAssistantError(
                f'Error fetching motion media "{self._system.system_id}": {err}'
            ) from err

            try:
                await self._hass.async_add_executor_job(
                    _write_image, snapshot_file, snapshot
                )
            except OSError as err:
                LOGGER.error("Can't write image to file: %s", err)


        async def save_clip_handler(call: ServiceCall) -> None:
            if self._attr_clip_url is None:
                return

            filename: Template = call.data.get(ATTR_FILENAME)
            filename.hass = self._hass
            clip_file = filename.async_render(variables={ATTR_ENTITY_ID: self})

            try:
                clip = await self._simplisafe.async_media_request(self._attr_clip_url)
            except SimplipyError as err:
                raise HomeAssistantError(
                f'Error fetching motion media "{self._system.system_id}": {err}'
            ) from err

            try:
                await self._hass.async_add_executor_job(
                    _write_image, clip_file, clip
                )
            except OSError as err:
                LOGGER.error("Can't write image to file: %s", err)

        self._hass.services.async_register(
            DOMAIN,
            SERVICE_OC_IMAGE,
            save_image_handler,
            schema=SERVICE_OC_IMAGE_SCHEMA,
        )

        self._hass.services.async_register(
            DOMAIN,
            SERVICE_OC_CLIP,
            save_clip_handler,
            schema=SERVICE_OC_CLIP_SCHEMA,
        )


    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Receive a Simplisafe WebsocketEvent aimed at me specifically, saving the media urls for later."""
        if event.event_type != EVENT_CAMERA_MOTION_DETECTED:
            return
        if event.sensor_type != DeviceTypes.OUTDOOR_CAMERA:
            return

        LOGGER.debug(
            "Outdoor Camera %s received a websocket event: %s",
            self._device.serial,
            event,
        )

        if event.media_urls is None:
            LOGGER.error("MISSING MEDIA URLS!")
            return

        self._attr_image_last_updated = event.timestamp
        self._attr_image_url = event.media_urls["image_url"]
        self._attr_clip_url = event.media_urls["clip_url"]
        self._attr_hls_url = event.media_urls["hls_url"]
        self._attr_cached_image = None

    def video_url(
        self,
        width: int,
        audio_encoding: str,
        **kwargs: Any,
    ) -> str | None:
        """The outdoor camera does not support video streaming."""
        return None
