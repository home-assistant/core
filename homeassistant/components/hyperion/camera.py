"""Switch platform for Hyperion."""

import asyncio
import base64
import binascii
import functools
import logging
from typing import Any, Callable, Dict, Optional, cast

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
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import get_hyperion_unique_id, listen_for_instance_updates
from .const import (
    CONF_INSTANCE_CLIENTS,
    DOMAIN,
    NAME_SUFFIX_HYPERION_CAMERA,
    SIGNAL_ENTITY_REMOVE,
    TYPE_HYPERION_CAMERA,
)

_LOGGER = logging.getLogger(__name__)

IMAGE_STREAM_JPG_SENTINEL = "data:image/jpg;base64,"


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities: Callable
) -> bool:
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
                    camera_unique_id(instance_num),
                    f"{instance_name} {NAME_SUFFIX_HYPERION_CAMERA}",
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
    return True


class HyperionCamera(Camera):
    """ComponentBinarySwitch switch class."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        hyperion_client: client.HyperionClient,
    ) -> None:
        """Initialize the switch."""
        super().__init__()  # type: ignore[no-untyped-call]
        self._unique_id = unique_id
        self._name = name
        self._client = hyperion_client

        self._image_cond = asyncio.Condition()
        self._image: Optional[bytes] = None
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

    @callback
    async def _update_imagestream(self, img: Optional[Dict[str, Any]] = None) -> None:
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

    async def _async_wait_for_camera_image(self) -> Optional[bytes]:
        """Return a single camera image in a stream."""
        if not self.available:
            return None
        async with self._image_cond:
            await self._image_cond.wait()
            if not self.available:
                return None
            return self._image

    async def _start_image_streaming_for_client(self) -> bool:
        """Start streaming for a client."""
        if (
            not self.is_streaming
            and not await self._client.async_send_image_stream_start()
        ):
            return False
        self.is_streaming = True
        self._image_stream_clients += 1
        return True

    async def _stop_image_streaming_for_client(self) -> None:
        """Stop streaming for a client."""
        self._image_stream_clients -= 1
        if self._image_stream_clients == 0:
            await self._client.async_send_image_stream_stop()
            self.is_streaming = False

    async def async_camera_image(self) -> Optional[bytes]:
        """Return single camera image bytes."""
        if not await self._start_image_streaming_for_client():
            return None
        image = await self._async_wait_for_camera_image()
        await self._stop_image_streaming_for_client()
        return image

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> Optional[web.StreamResponse]:
        """Serve an HTTP MJPEG stream from the camera."""
        if not await self._start_image_streaming_for_client():
            return None
        try:
            response = await async_get_still_stream(
                request, self._async_wait_for_camera_image, DEFAULT_CONTENT_TYPE, 0.0
            )  # type: ignore[no-untyped-call]
        finally:
            await self._stop_image_streaming_for_client()
        return cast(Optional[web.StreamResponse], response)

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        assert self.hass
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


CAMERA_TYPES = {
    TYPE_HYPERION_CAMERA: HyperionCamera,
}
