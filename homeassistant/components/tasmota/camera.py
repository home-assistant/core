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
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate, TasmotaEntity

TIMEOUT = 10
BUFFER_SIZE = 102400

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    """An implementation of an IP camera that is reachable over a URL."""

    _tasmota_entity: tasmota_camera.TasmotaCamera

    """Representation of a Tasmota Camera."""
    fps: int = 0
    failure: str = ""

    def __init__(self, **kwds: Any) -> None:
        """Initialize a MJPEG camera."""
        super().__init__(
            **kwds,
        )
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

        except TimeoutError:
            _LOGGER.error("Timeout getting camera image from %s", self.name)

        except aiohttp.ClientError as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self.name, err)

        return None

    async def handle_async_mjpeg_stream(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        # connect to stream
        websession = async_get_clientsession(self.hass)
        stream_coro = self._tasmota_entity.get_mjpeg_stream(websession)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.camera_state_updated)
        await super().async_added_to_hass()

    @callback
    def camera_state_updated(self, state: Any, **kwargs: Any) -> None:
        """Handle state updates."""
        if state.get("CamFail"):
            self.failure = "Camera Failure"
        elif state.get("JpegFail"):
            self.failure = "JPEG Failure"
        else:
            self.failure = ""
        if "FPS" in state:
            self.fps = state["FPS"]
        self.async_write_ha_state()

    @property
    def state(self) -> str:
        """Override state reporting to report failures and FPS if available."""
        if self.failure:
            return self.failure
        if self.fps:
            return f"{self.fps} FPS"
        return super().state
