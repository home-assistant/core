"""Switch platform for Hyperion."""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import functools
import logging
from typing import Any

from aiohttp import web
from hyperion import client
from hyperion.const import (
    KEY_IMAGE,
    KEY_IMAGE_STREAM,
    KEY_LEDCOLORS,
    KEY_RESULT,
    KEY_UPDATE,
)

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    Camera,
    async_get_still_stream,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    get_hyperion_device_id,
    get_hyperion_unique_id,
    listen_for_instance_updates,
)
from .const import (
    CONF_INSTANCE_CLIENTS,
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    NAME_SUFFIX_HYPERION_CAMERA,
    SIGNAL_ENTITY_REMOVE,
    TYPE_HYPERION_CAMERA,
)

_LOGGER = logging.getLogger(__name__)

IMAGE_STREAM_JPG_SENTINEL = "data:image/jpg;base64,"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Hyperion platform from config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    server_id = config_entry.unique_id

    def camera_unique_id(instance_num: int) -> str:
        """Return the camera unique_id."""
        assert server_id
        return get_hyperion_unique_id(server_id, instance_num, TYPE_HYPERION_CAMERA)

    @callback
    def instance_add(instance_num: int, instance_name: str) -> None:
        """Add entities for a new Hyperion instance."""
        assert server_id
        async_add_entities(
            [
                HyperionCamera(
                    server_id,
                    instance_num,
                    instance_name,
                    entry_data[CONF_INSTANCE_CLIENTS][instance_num],
                )
            ]
        )

    @callback
    def instance_remove(instance_num: int) -> None:
        """Remove entities for an old Hyperion instance."""
        assert server_id
        async_dispatcher_send(
            hass,
            SIGNAL_ENTITY_REMOVE.format(
                camera_unique_id(instance_num),
            ),
        )

    listen_for_instance_updates(hass, config_entry, instance_add, instance_remove)


# A note on Hyperion streaming semantics:
#
# Different Hyperion priorities behave different with regards to streaming. Colors will
# not stream (as there is nothing to stream). External grabbers (e.g. USB Capture) will
# stream what is being captured. Some effects (based on GIFs) will stream, others will
# not. In cases when streaming is not supported from a selected priority, there is no
# notification beyond the failure of new frames to arrive.


class HyperionCamera(Camera):
    """ComponentBinarySwitch switch class."""

    def __init__(
        self,
        server_id: str,
        instance_num: int,
        instance_name: str,
        hyperion_client: client.HyperionClient,
    ) -> None:
        """Initialize the switch."""
        super().__init__()

        self._unique_id = get_hyperion_unique_id(
            server_id, instance_num, TYPE_HYPERION_CAMERA
        )
        self._name = f"{instance_name} {NAME_SUFFIX_HYPERION_CAMERA}".strip()
        self._device_id = get_hyperion_device_id(server_id, instance_num)
        self._instance_name = instance_name
        self._client = hyperion_client

        self._image_cond = asyncio.Condition()
        self._image: bytes | None = None

        # The number of open streams, when zero the stream is stopped.
        self._image_stream_clients = 0

        self._client_callbacks = {
            f"{KEY_LEDCOLORS}-{KEY_IMAGE_STREAM}-{KEY_UPDATE}": self._update_imagestream
        }

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if the camera is on."""
        return self.available

    @property
    def available(self) -> bool:
        """Return server availability."""
        return bool(self._client.has_loaded_state)

    async def _update_imagestream(self, img: dict[str, Any] | None = None) -> None:
        """Update Hyperion components."""
        if not img:
            return
        img_data = img.get(KEY_RESULT, {}).get(KEY_IMAGE)
        if not img_data or not img_data.startswith(IMAGE_STREAM_JPG_SENTINEL):
            return
        async with self._image_cond:
            try:
                self._image = base64.b64decode(
                    img_data[len(IMAGE_STREAM_JPG_SENTINEL) :]
                )
            except binascii.Error:
                return
            self._image_cond.notify_all()

    async def _async_wait_for_camera_image(self) -> bytes | None:
        """Return a single camera image in a stream."""
        async with self._image_cond:
            await self._image_cond.wait()
            return self._image if self.available else None

    async def _start_image_streaming_for_client(self) -> bool:
        """Start streaming for a client."""
        if (
            not self._image_stream_clients
            and not await self._client.async_send_image_stream_start()
        ):
            return False

        self._image_stream_clients += 1
        self.is_streaming = True
        self.async_write_ha_state()
        return True

    async def _stop_image_streaming_for_client(self) -> None:
        """Stop streaming for a client."""
        self._image_stream_clients -= 1

        if not self._image_stream_clients:
            await self._client.async_send_image_stream_stop()
            self.is_streaming = False
            self.async_write_ha_state()

    @asynccontextmanager
    async def _image_streaming(self) -> AsyncGenerator:
        """Async context manager to start/stop image streaming."""
        try:
            yield await self._start_image_streaming_for_client()
        finally:
            await self._stop_image_streaming_for_client()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return single camera image bytes."""
        async with self._image_streaming() as is_streaming:
            if is_streaming:
                return await self._async_wait_for_camera_image()
        return None

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Serve an HTTP MJPEG stream from the camera."""
        async with self._image_streaming() as is_streaming:
            if is_streaming:
                return await async_get_still_stream(
                    request,
                    self._async_wait_for_camera_image,
                    DEFAULT_CONTENT_TYPE,
                    0.0,
                )
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self._unique_id),
                functools.partial(self.async_remove, force_remove=True),
            )
        )

        self._client.add_callbacks(self._client_callbacks)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup prior to hass removal."""
        self._client.remove_callbacks(self._client_callbacks)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._instance_name,
            "manufacturer": HYPERION_MANUFACTURER_NAME,
            "model": HYPERION_MODEL_NAME,
        }


CAMERA_TYPES = {
    TYPE_HYPERION_CAMERA: HyperionCamera,
}
