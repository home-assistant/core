"""Support for ONVIF Cameras with FFmpeg as decoder."""
import asyncio

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS, DATA_FFMPEG
from homeassistant.const import HTTP_BASIC_AUTHENTICATION
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

from .base import ONVIFBaseEntity
from .const import (
    ABSOLUTE_MOVE,
    ATTR_CONTINUOUS_DURATION,
    ATTR_DISTANCE,
    ATTR_MOVE_MODE,
    ATTR_PAN,
    ATTR_PRESET,
    ATTR_SPEED,
    ATTR_TILT,
    ATTR_ZOOM,
    CONF_RTSP_TRANSPORT,
    CONF_SNAPSHOT_AUTH,
    CONTINUOUS_MOVE,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DOMAIN,
    GOTOPRESET_MOVE,
    LOGGER,
    RELATIVE_MOVE,
    SERVICE_PTZ,
    ZOOM_IN,
    ZOOM_OUT,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ONVIF camera video stream."""
    platform = entity_platform.current_platform.get()

    # Create PTZ service
    platform.async_register_entity_service(
        SERVICE_PTZ,
        {
            vol.Optional(ATTR_PAN): vol.In([DIR_LEFT, DIR_RIGHT]),
            vol.Optional(ATTR_TILT): vol.In([DIR_UP, DIR_DOWN]),
            vol.Optional(ATTR_ZOOM): vol.In([ZOOM_OUT, ZOOM_IN]),
            vol.Optional(ATTR_DISTANCE, default=0.1): cv.small_float,
            vol.Optional(ATTR_SPEED, default=0.5): cv.small_float,
            vol.Optional(ATTR_MOVE_MODE, default=RELATIVE_MOVE): vol.In(
                [CONTINUOUS_MOVE, RELATIVE_MOVE, ABSOLUTE_MOVE, GOTOPRESET_MOVE]
            ),
            vol.Optional(ATTR_CONTINUOUS_DURATION, default=0.5): cv.small_float,
            vol.Optional(ATTR_PRESET, default="0"): cv.string,
        },
        "async_perform_ptz",
    )

    device = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities(
        [ONVIFCameraEntity(device, profile) for profile in device.profiles]
    )

    return True


class ONVIFCameraEntity(ONVIFBaseEntity, Camera):
    """Representation of an ONVIF camera."""

    def __init__(self, device, profile):
        """Initialize ONVIF camera entity."""
        ONVIFBaseEntity.__init__(self, device, profile)
        Camera.__init__(self)
        self.stream_options[CONF_RTSP_TRANSPORT] = device.config_entry.options.get(
            CONF_RTSP_TRANSPORT
        )
        self._basic_auth = (
            device.config_entry.data.get(CONF_SNAPSHOT_AUTH)
            == HTTP_BASIC_AUTHENTICATION
        )
        self._stream_uri = None
        self._snapshot_uri = None

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return SUPPORT_STREAM

    @property
    def name(self) -> str:
        """Return the name of this camera."""
        return f"{self.device.name} - {self.profile.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.profile.index:
            return f"{self.device.info.mac or self.device.info.serial_number}_{self.profile.index}"
        return self.device.info.mac or self.device.info.serial_number

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.device.max_resolution == self.profile.video.resolution.width

    async def stream_source(self):
        """Return the stream source."""
        return self._stream_uri

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        image = None

        if self.device.capabilities.snapshot:
            auth = None
            if self.device.username and self.device.password:
                if self._basic_auth:
                    auth = HTTPBasicAuth(self.device.username, self.device.password)
                else:
                    auth = HTTPDigestAuth(self.device.username, self.device.password)

            def fetch():
                """Read image from a URL."""
                try:
                    response = requests.get(self._snapshot_uri, timeout=5, auth=auth)
                    if response.status_code < 300:
                        return response.content
                except requests.exceptions.RequestException as error:
                    LOGGER.error(
                        "Fetch snapshot image failed from %s, falling back to FFmpeg; %s",
                        self.device.name,
                        error,
                    )

                return None

            image = await self.hass.async_add_executor_job(fetch)

        if image is None:
            ffmpeg = ImageFrame(self.hass.data[DATA_FFMPEG].binary, loop=self.hass.loop)
            image = await asyncio.shield(
                ffmpeg.get_image(
                    self._stream_uri,
                    output_format=IMAGE_JPEG,
                    extra_cmd=self.device.config_entry.options.get(
                        CONF_EXTRA_ARGUMENTS
                    ),
                )
            )

        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        LOGGER.debug("Handling mjpeg stream from camera '%s'", self.device.name)

        ffmpeg_manager = self.hass.data[DATA_FFMPEG]
        stream = CameraMjpeg(ffmpeg_manager.binary, loop=self.hass.loop)

        await stream.open_camera(
            self._stream_uri,
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

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        uri_no_auth = await self.device.async_get_stream_uri(self.profile)
        self._stream_uri = uri_no_auth.replace(
            "rtsp://", f"rtsp://{self.device.username}:{self.device.password}@", 1
        )

        if self.device.capabilities.snapshot:
            self._snapshot_uri = await self.device.async_get_snapshot_uri(self.profile)

    async def async_perform_ptz(
        self,
        distance,
        speed,
        move_mode,
        continuous_duration,
        preset,
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
