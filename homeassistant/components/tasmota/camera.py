"""Support for Tasmota Camera."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from hatasmota import camera as tasmota_camera
from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.models import DiscoveryHashType

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate, TasmotaEntity

TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota light dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota camera."""
        async_add_entities(
            [
                TasmotaCamera(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(camera.DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(camera.DOMAIN),
            async_discover,
        )
    )


class TasmotaCamera(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    TasmotaEntity,
    Camera,
):
    """Representation of a Tasmota Camera."""

    _tasmota_entity: tasmota_camera.TasmotaCamera

    def __init__(self, **kwds: Any) -> None:
        """Initialize."""
        super().__init__(**kwds)
        Camera.__init__(self)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""

        websession = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(TIMEOUT):
                response = await self._tasmota_entity.get_still_image_stream(websession)
                return await response.read()

        except TimeoutError as err:
            raise HomeAssistantError(
                f"Timeout getting camera image from {self.name}: {err}"
            ) from err

        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                f"Error getting new camera image from {self.name}: {err}"
            ) from err

        return None

    async def handle_async_mjpeg_stream(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        # connect to stream
        websession = async_get_clientsession(self.hass)
        stream_coro = self._tasmota_entity.get_mjpeg_stream(websession)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)
