"""
This component provides support to the Logi Circle camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.logi_circle/
"""
from datetime import timedelta
import logging

from homeassistant.components.camera import (
    ATTR_ENTITY_ID, SUPPORT_ON_OFF, Camera)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.components.logi_circle.const import (
    ATTR_API, CONF_ATTRIBUTION, CONF_CAMERAS, CONF_FFMPEG_ARGUMENTS,
    DEVICE_BRAND, DOMAIN as LOGI_CIRCLE_DOMAIN, LED_MODE_KEY,
    RECORDING_MODE_KEY)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

DEPENDENCIES = ['logi_circle', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up a camera for a Logi Circle device. Obsolete."""
    _LOGGER.warning(
        "Logi Circle no longer works with camera platform configuration")


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle Camera based on a config entry."""
    devices = await hass.data[LOGI_CIRCLE_DOMAIN][ATTR_API].cameras
    ffmpeg = hass.data[DATA_FFMPEG]

    cameras = [LogiCam(device, entry, ffmpeg)
               for device in devices]

    async_add_entities(cameras, True)


class LogiCam(Camera):
    """An implementation of a Logi Circle camera."""

    def __init__(self, camera, device_info, ffmpeg):
        """Initialize Logi Circle camera."""
        super().__init__()
        self._camera = camera
        self._name = self._camera.name
        self._id = self._camera.id
        self._ffmpeg = ffmpeg
        self._ffmpeg_arguments = device_info.data.get(
            CONF_CAMERAS).get(CONF_FFMPEG_ARGUMENTS)

    async def async_added_to_hass(self):
        """Make entity globally accessible for use in service handler."""
        self.hass.data[LOGI_CIRCLE_DOMAIN]['entities']['camera'].append(self)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def supported_features(self):
        """Logi Circle camera's support turning on and off ("soft" switch)."""
        return SUPPORT_ON_OFF

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            'name': self._name,
            'identifiers': {
                (LOGI_CIRCLE_DOMAIN, self._camera.id)
            },
            'model': self._camera.model_name,
            'sw_version': self._camera.firmware,
            'manufacturer': DEVICE_BRAND
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }

    async def async_camera_image(self):
        """Return a still image from the camera."""
        return await self._camera.live_stream.download_jpeg()

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera's live stream."""
        from haffmpeg import CameraMjpeg

        live_stream = await self._camera.live_stream.get_rtsp_url()

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        # Extend the timeout if device is in deep sleep
        timeout = 60 if self._camera.pir_wake_up else 10

        await stream.open_camera(
            live_stream, extra_cmd=self._ffmpeg_arguments)

        try:
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream,
                'multipart/x-mixed-replace;boundary=ffserver', timeout=timeout)
        finally:
            await stream.close()

    async def async_turn_off(self):
        """Disable streaming mode for this camera."""
        await self._camera.set_config('streaming', False)

    async def async_turn_on(self):
        """Enable streaming mode for this camera."""
        await self._camera.set_config('streaming', True)

    @property
    def should_poll(self):
        """Update the image periodically."""
        return True

    @property
    def is_on(self):
        """Return true if on."""
        return self._camera.connected and self._camera.streaming

    async def set_config(self, mode, value):
        """Set an configuration property for the target camera."""
        if mode == LED_MODE_KEY:
            await self._camera.set_config('led', value)
        if mode == RECORDING_MODE_KEY:
            await self._camera.set_config('recording_disabled', not value)

    async def download_livestream(self, filename, duration):
        """Download a recording from the camera's livestream."""
        # Render filename from template.
        filename.hass = self.hass
        stream_file = filename.async_render(
            variables={ATTR_ENTITY_ID: self.entity_id})

        # Respect configured path whitelist.
        if not self.hass.config.is_allowed_path(stream_file):
            _LOGGER.error(
                "Can't write %s, no access to path!", stream_file)
            return

        await self._camera.live_stream.download_rtsp(
            filename=stream_file,
            duration=timedelta(seconds=duration),
            ffmpeg_bin=self._ffmpeg.binary)

    async def livestream_snapshot(self, filename):
        """Download a still frame from the camera's livestream."""
        # Render filename from template.
        filename.hass = self.hass
        snapshot_file = filename.async_render(
            variables={ATTR_ENTITY_ID: self.entity_id})

        # Respect configured path whitelist.
        if not self.hass.config.is_allowed_path(snapshot_file):
            _LOGGER.error(
                "Can't write %s, no access to path!", snapshot_file)
            return

        await self._camera.live_stream.download_jpeg(
            filename=snapshot_file,
            refresh=True)
