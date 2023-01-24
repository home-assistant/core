"""Support for viewing the camera feed from a DoorBird video doorbell."""
from __future__ import annotations

import asyncio
import datetime
import logging

import aiohttp
from aiohttp import web
import async_timeout

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import (
    CONF_MJPEG_VIDEO,
    DOMAIN,
    DOOR_STATION,
    DOOR_STATION_EVENT_ENTITY_IDS,
    DOOR_STATION_INFO,
)
from .entity import DoorBirdEntity

_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=2)
_LAST_MOTION_INTERVAL = datetime.timedelta(seconds=30)
_LIVE_INTERVAL = datetime.timedelta(seconds=45)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 15  # seconds


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DoorBird camera platform."""
    config_entry_id = config_entry.entry_id
    mjpeg_video = config_entry.data[CONF_MJPEG_VIDEO]
    config_data = hass.data[DOMAIN][config_entry_id]
    doorstation = config_data[DOOR_STATION]
    doorstation_info = config_data[DOOR_STATION_INFO]
    device = doorstation.device

    async_add_entities(
        [
            DoorBirdCamera(
                doorstation,
                doorstation_info,
                device.live_image_url,
                "live",
                f"{doorstation.name} Live",
                doorstation.doorstation_events,
                _LIVE_INTERVAL,
                device.live_video_url if mjpeg_video else device.rtsp_live_video_url,
                mjpeg_video,
            ),
            DoorBirdCamera(
                doorstation,
                doorstation_info,
                device.history_image_url(1, "doorbell"),
                "last_ring",
                f"{doorstation.name} Last Ring",
                [],
                _LAST_VISITOR_INTERVAL,
            ),
            DoorBirdCamera(
                doorstation,
                doorstation_info,
                device.history_image_url(1, "motionsensor"),
                "last_motion",
                f"{doorstation.name} Last Motion",
                [],
                _LAST_MOTION_INTERVAL,
            ),
        ]
    )


class DoorBirdCamera(DoorBirdEntity, Camera):
    """The camera on a DoorBird device."""

    def __init__(
        self,
        doorstation,
        doorstation_info,
        url,
        camera_id,
        name,
        doorstation_events,
        interval,
        stream_url=None,
        mjpeg_video=False,
    ) -> None:
        """Initialize the camera on a DoorBird device."""
        super().__init__(doorstation, doorstation_info)
        self._url = url

        if mjpeg_video:
            self._mjpeg_url = stream_url
            self._stream_url = None
        else:
            self._stream_url = stream_url

        self._attr_name = name
        self._last_image: bytes | None = None
        if self._stream_url:
            self._attr_supported_features = CameraEntityFeature.STREAM
        self._interval = interval
        self._last_update = datetime.datetime.min
        self._attr_unique_id = f"{self._mac_addr}_{camera_id}"
        self._doorstation_events = doorstation_events

    async def stream_source(self):
        """Return the stream source."""
        return self._stream_url

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""

        # connect to stream
        websession = async_get_clientsession(self.hass, verify_ssl=True)
        stream_coro = websession.get(self._mjpeg_url)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Pull a still image from the camera."""
        now = dt_util.utcnow()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            websession = async_get_clientsession(self.hass)
            async with async_timeout.timeout(_TIMEOUT):
                response = await websession.get(self._url)

            self._last_image = await response.read()
            self._last_update = now
            return self._last_image
        except asyncio.TimeoutError:
            _LOGGER.error("DoorBird %s: Camera image timed out", self.name)
            return self._last_image
        except aiohttp.ClientError as error:
            _LOGGER.error(
                "DoorBird %s: Error getting camera image: %s", self.name, error
            )
            return self._last_image

    async def async_added_to_hass(self) -> None:
        """Add callback after being added to hass.

        Registers entity_id map for the logbook
        """
        event_to_entity_id = self.hass.data[DOMAIN].setdefault(
            DOOR_STATION_EVENT_ENTITY_IDS, {}
        )
        for event in self._doorstation_events:
            event_to_entity_id[event] = self.entity_id

    async def will_remove_from_hass(self):
        """Unregister entity_id map for the logbook."""
        event_to_entity_id = self.hass.data[DOMAIN][DOOR_STATION_EVENT_ENTITY_IDS]
        for event in self._doorstation_events:
            if event in event_to_entity_id:
                del event_to_entity_id[event]
