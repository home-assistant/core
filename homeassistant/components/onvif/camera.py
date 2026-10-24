"""Support for ONVIF Cameras with FFmpeg as decoder."""

import asyncio
from typing import override

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from onvif.exceptions import ONVIFError
from yarl import URL

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS, get_ffmpeg_manager
from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
    RTSP_TRANSPORTS,
)
from homeassistant.const import HTTP_BASIC_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SNAPSHOT_AUTH, LOGGER
from .device import ONVIFConfigEntry, ONVIFDevice
from .entity import ONVIFBaseEntity
from .models import Profile
from .util import build_profile_unique_keys


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ONVIFConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ONVIF camera video stream."""
    device = config_entry.runtime_data
    unique_keys = build_profile_unique_keys(device.profiles)
    async_add_entities(
        [
            ONVIFCameraEntity(device, profile, unique_keys[profile.token])
            for profile in device.profiles
        ]
    )


class ONVIFCameraEntity(ONVIFBaseEntity, Camera):
    """Representation of an ONVIF camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, device: ONVIFDevice, profile: Profile, unique_key: str) -> None:
        """Initialize ONVIF camera entity."""
        ONVIFBaseEntity.__init__(self, device)
        Camera.__init__(self)
        self.profile = profile
        self.stream_options[CONF_RTSP_TRANSPORT] = device.config_entry.options.get(
            CONF_RTSP_TRANSPORT, next(iter(RTSP_TRANSPORTS))
        )
        self.stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = (
            device.config_entry.options.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS, False)
        )
        self._basic_auth = (
            device.config_entry.data.get(CONF_SNAPSHOT_AUTH)
            == HTTP_BASIC_AUTHENTICATION
        )
        self._stream_uri: str | None = None
        self._stream_uri_future: asyncio.Future[str] | None = None
        self._attr_entity_registry_enabled_default = (
            device.max_resolution == profile.video.resolution.width
        )
        self._attr_unique_id = f"{self.mac_or_serial}#{unique_key}"
        self._attr_name = f"{device.name} {profile.name}"

    @property
    @override
    def use_stream_for_stills(self) -> bool:
        """Whether or not to use stream to generate stills."""
        return bool(self.stream and self.stream.dynamic_stream_settings.preload_stream)

    @override
    async def stream_source(self) -> str | None:
        """Return the stream source."""
        return await self._async_get_stream_uri()

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""

        if self.device.capabilities.snapshot:
            try:
                if image := await self.device.device.get_snapshot(
                    self.profile.token, self._basic_auth
                ):
                    return image
            # pylint: disable-next=home-assistant-action-swallowed-exception
            except ONVIFError as err:
                LOGGER.error(
                    "Fetch snapshot image failed from %s, falling back to FFmpeg; %s",
                    self.device.name,
                    err,
                )
            else:
                LOGGER.error(
                    "Fetch snapshot image failed from %s, falling back to FFmpeg",
                    self.device.name,
                )

        stream_uri = await self._async_get_stream_uri()
        return await ffmpeg.async_get_image(
            self.hass,
            stream_uri,
            extra_cmd=self.device.config_entry.options.get(CONF_EXTRA_ARGUMENTS),
            width=width,
            height=height,
        )

    @override
    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        LOGGER.debug("Handling mjpeg stream from camera '%s'", self.device.name)

        ffmpeg_manager = get_ffmpeg_manager(self.hass)
        stream = CameraMjpeg(ffmpeg_manager.binary)
        stream_uri = await self._async_get_stream_uri()

        await stream.open_camera(
            stream_uri,
            extra_cmd=self.device.config_entry.options.get(CONF_EXTRA_ARGUMENTS),
        )

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                ffmpeg_manager.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    async def _async_get_stream_uri(self) -> str:
        """Return the stream URI."""
        if self._stream_uri:
            return self._stream_uri
        if self._stream_uri_future:
            return await self._stream_uri_future
        loop = asyncio.get_running_loop()
        self._stream_uri_future = loop.create_future()
        try:
            uri_no_auth = await self.device.async_get_stream_uri(self.profile)
        except (TimeoutError, Exception) as err:
            LOGGER.error("Failed to get stream uri: %s", err)
            if self._stream_uri_future:
                self._stream_uri_future.set_exception(err)
            raise
        url = URL(uri_no_auth)
        url = url.with_user(self.device.username)
        url = url.with_password(self.device.password)
        self._stream_uri = str(url)
        self._stream_uri_future.set_result(self._stream_uri)
        return self._stream_uri

    async def async_perform_ptz(
        self,
        distance,
        move_mode,
        continuous_duration,
        preset,
        speed=None,
        pan=None,
        tilt=None,
        zoom=None,
    ) -> None:
        """Perform a PTZ action on the camera."""
        await self.device.async_perform_ptz(
            self.profile,
            distance,
            speed,
            move_mode,
            continuous_duration,
            preset,
            pan,
            tilt,
            zoom,
        )
