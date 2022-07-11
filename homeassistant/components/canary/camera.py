"""Support for Canary camera."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from aiohttp.web import Request, StreamResponse
from canary.const import HEADER_VALUE_AUTHORIZATION, HEADER_VALUE_USER_AGENT
from canary.live_stream_api import LiveStreamSession
from canary.model import Device, Entry, Location
from haffmpeg.camera import CameraMjpeg
import httpx
import voluptuous as vol

from homeassistant.components import ffmpeg
from homeassistant.components.camera import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    Camera,
)
from homeassistant.components.ffmpeg import FFmpegManager, get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import Throttle, dt as dt_util

from ...helpers.httpx_client import get_async_client
from .const import (
    CONF_ENTRY_TIMEOUT_HOURS,
    CONF_FFMPEG_ARGUMENTS,
    DATA_COORDINATOR,
    DEFAULT_ENTRY_TIMEOUT_HOURS,
    DEFAULT_FFMPEG_ARGUMENTS,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import CanaryDataUpdateCoordinator

MIN_TIME_BETWEEN_SESSION_RENEW: Final = timedelta(seconds=90)
FORCE_CAMERA_REFRESH_INTERVAL: Final = timedelta(minutes=15)

PLATFORM_SCHEMA: Final = vol.All(
    cv.deprecated(CONF_FFMPEG_ARGUMENTS),
    PARENT_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(
                CONF_FFMPEG_ARGUMENTS, default=DEFAULT_FFMPEG_ARGUMENTS
            ): cv.string,
            vol.Optional(
                CONF_ENTRY_TIMEOUT_HOURS, default=DEFAULT_ENTRY_TIMEOUT_HOURS
            ): cv.positive_int,
        }
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canary sensors based on a config entry."""
    coordinator: CanaryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    ffmpeg_arguments: str = entry.options.get(
        CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
    )
    entry_timeout_hours: int = entry.options.get(
        CONF_ENTRY_TIMEOUT_HOURS, DEFAULT_ENTRY_TIMEOUT_HOURS
    )
    entry_image_expiration_interval = timedelta(hours=entry_timeout_hours)
    cameras: list[CanaryCamera] = []

    for location_id, location in coordinator.data["locations"].items():
        for device in location.devices:
            if device.is_online:
                cameras.append(
                    CanaryCamera(
                        hass,
                        coordinator,
                        location_id,
                        device,
                        ffmpeg_arguments,
                        entry_image_expiration_interval,
                    )
                )

    async_add_entities(cameras, True)


class CanaryCamera(CoordinatorEntity[CanaryDataUpdateCoordinator], Camera):
    """An implementation of a Canary security camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: CanaryDataUpdateCoordinator,
        location_id: str,
        device: Device,
        ffmpeg_args: str,
        entry_image_expiration_interval: timedelta,
    ) -> None:
        """Initialize a Canary security camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._ffmpeg: FFmpegManager = get_ffmpeg_manager(hass)
        self._ffmpeg_arguments = ffmpeg_args
        self._entry_image_expiration_interval = entry_image_expiration_interval
        self._location_id = location_id
        self._device = device
        self._live_stream_session: LiveStreamSession | None = None
        self._attr_name = device.name
        self._attr_unique_id = str(device.device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            manufacturer=MANUFACTURER,
            model=device.device_type["name"],
            name=device.name,
        )
        self._image: bytes | None = None
        self._last_event: Entry | None = None
        self._last_image_id = None
        self._image_url: str | None = None
        self._expires_at = dt_util.utcnow()
        _LOGGER.debug(
            "%s %s has been initialized", self.name, device.device_type["name"]
        )

    @property
    def name(self) -> str:
        """Name of sensor."""
        return str(self._attr_name)

    @property
    def location(self) -> Location:
        """Return information about the location."""
        return self.coordinator.data["locations"][self._location_id]

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self.location.is_recording  # type: ignore[no-any-return]

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return not self.location.is_recording

    def _headers_for_ffmpeg(self) -> str:
        token = (
            None
            if self._live_stream_session is None
            else self._live_stream_session.auth_token
        )
        if token:
            return " ".join(
                [
                    f'-user_agent "{HEADER_VALUE_USER_AGENT}"',
                    f'-headers "{HEADER_VALUE_AUTHORIZATION} {token}"',
                ]
            )
        return ""

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera or the last image captured by an 'entry' event."""

        await self._check_for_new_image()

        if self._image_url is not None:
            await self._get_entry_image()

        utcnow = dt_util.utcnow()
        if self._expires_at <= utcnow:
            # if we still don't have an image, grab the live view
            _LOGGER.debug("Grabbing a live view image from %s", self.name)
            await self.hass.async_add_executor_job(self.renew_live_stream_session)

            if (live_stream_session := self._live_stream_session) is None:
                return None

            if not (live_stream_url := live_stream_session.live_stream_url):
                return None

            ffmpeg_args = f"{self._ffmpeg_arguments} {self._headers_for_ffmpeg()}"
            image = await ffmpeg.async_get_image(
                self.hass,
                live_stream_url,
                extra_cmd=ffmpeg_args,
                width=width,
                height=height,
            )

            if image:
                self._image = image
                self._expires_at = FORCE_CAMERA_REFRESH_INTERVAL + utcnow
                _LOGGER.debug("Grabbed a live view image from %s", self.name)
            await self.hass.async_add_executor_job(live_stream_session.stop_session)
            _LOGGER.debug("Stopped live session from %s", self.name)

        return self._image

    async def _get_entry_image(self) -> None:
        # grab the latest entry image
        _LOGGER.debug("Getting the latest entry image for %s", self.name)
        try:
            if (image_url := self._image_url) is not None:
                _LOGGER.debug("getting image for %s: %s", self.name, image_url)
                async_client = get_async_client(self.hass)
                response = await async_client.get(image_url, timeout=10)
                response.raise_for_status()
                utcnow = dt_util.utcnow()
                self._image = response.content
                # expire the image after a user configurable amount of time and get live images every 15 minutes
                self._expires_at = utcnow + self._entry_image_expiration_interval
                self._last_image_id = (
                    None if self._last_event is None else self._last_event.entry_id
                )
                self._image_url = None
                _LOGGER.debug("Got the latest entry image for %s", self.name)
        except httpx.TimeoutException:
            _LOGGER.error("Timeout getting camera image from %s", self.name)
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self.name, err)

    async def _check_for_new_image(self) -> None:
        """
        Get the latest entry event if one exists.

        Free users only get a 3-hour window of events, so we can't expire images as if something happens are 11:20pm
        after 2:20am it would no longer return in API calls. So we expire the image after a configurable amount of time
        (defaults to 14 hours).
        """

        await self._set_last_event()

        if self._last_event is None:
            return

        if self._last_image_id != self._last_event.entry_id:
            try:
                self._image_url = self._last_event.thumbnails[0].image_url
            except IndexError:
                self._image_url = None

    async def _set_last_event(self) -> None:
        """Set the self._last_event to the latest event entry."""
        if self._last_event is None:
            self._last_event = await self._get_latest_entry()
        else:
            last_event = await self._get_latest_entry()
            if last_event is not None:
                if self._last_event.entry_id != last_event.entry_id:
                    self._last_event = last_event

    async def _get_latest_entry(self) -> Entry | None:
        """Get the latest entry event if one exists."""
        try:
            last_event = self.coordinator.data["entries"][self._device.device_id][0]
            return last_event
        except KeyError:
            return None
        except IndexError:
            return None

    async def handle_async_mjpeg_stream(
        self, request: Request
    ) -> StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        await self.hass.async_add_executor_job(self.renew_live_stream_session)

        if (live_stream_session := self._live_stream_session) is None:
            return None

        if not (live_stream_url := live_stream_session.live_stream_url):
            return None

        _LOGGER.debug("Starting connection to %s at %s", self.name, live_stream_url)

        ffmpeg_args = f"{self._ffmpeg_arguments} {self._headers_for_ffmpeg()}"
        stream = CameraMjpeg(self._ffmpeg.binary)
        await stream.open_camera(live_stream_url, extra_cmd=ffmpeg_args)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            _LOGGER.debug(
                "Stopping the live stream on %s to %s", self.name, live_stream_url
            )
            await stream.close()
            await self.hass.async_add_executor_job(live_stream_session.stop_session)
            _LOGGER.debug(
                "Streaming connection closed on %s to %s",
                self.name,
                live_stream_url,
            )

    @Throttle(MIN_TIME_BETWEEN_SESSION_RENEW)
    def renew_live_stream_session(self) -> None:
        """Renew live stream session."""
        self._live_stream_session = self.coordinator.canary.get_live_stream_session(
            self._device
        )

        _LOGGER.debug(
            "Live Stream URL for %s is %s",
            self.name,
            self._live_stream_session.live_stream_url,
        )
