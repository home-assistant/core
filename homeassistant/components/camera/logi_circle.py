"""
This component provides support to the Logi Circle camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.logi_circle/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.components.logi_circle.const import (
    CONF_ATTRIBUTION, CONF_CAMERAS, CONF_FFMPEG_ARGUMENTS, DEVICE_BRAND,
    DOMAIN as LOGI_CIRCLE_DOMAIN)
from homeassistant.components.camera import (
    Camera, CAMERA_SERVICE_SCHEMA, SUPPORT_ON_OFF,
    ATTR_ENTITY_ID, ATTR_FILENAME, DOMAIN)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

DEPENDENCIES = ['logi_circle', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_PRIVACY_MODE = 'logi_circle_set_privacy_mode'
SERVICE_LIVESTREAM_SNAPSHOT = 'logi_circle_livestream_snapshot'
SERVICE_LIVESTREAM_RECORD = 'logi_circle_livestream_record'
DATA_KEY = 'camera.logi_circle'

ATTR_VALUE = 'value'
ATTR_DURATION = 'duration'

LOGI_CIRCLE_SERVICE_SET_PRIVACY_MODE = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_VALUE): cv.boolean
})

LOGI_CIRCLE_SERVICE_SNAPSHOT = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template
})

LOGI_CIRCLE_SERVICE_RECORD = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template,
    vol.Required(ATTR_DURATION): cv.positive_int
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up a camera for a Logi Circle device. Obsolete."""
    _LOGGER.warning(
        'Logi Circle no longer works with camera platform configuration.')


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle Camera based on a config entry."""

    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    ffmpeg = hass.data[DATA_FFMPEG]

    cameras = [LogiCam(device, entry, ffmpeg)
               for device in devices]

    async_add_entities(cameras, True)

    async def service_handler(service):
        """Dispatch service calls to target entities."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            target_devices = [dev for dev in cameras
                              if dev.entity_id in entity_ids]
        else:
            target_devices = cameras

        for target_device in target_devices:
            if service.service == SERVICE_SET_PRIVACY_MODE:
                await target_device.set_privacy_mode(**params)
            if service.service == SERVICE_LIVESTREAM_SNAPSHOT:
                await target_device.livestream_snapshot(**params)
            if service.service == SERVICE_LIVESTREAM_RECORD:
                await target_device.download_livestream(**params)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_PRIVACY_MODE, service_handler,
        schema=LOGI_CIRCLE_SERVICE_SET_PRIVACY_MODE)

    hass.services.async_register(
        DOMAIN, SERVICE_LIVESTREAM_SNAPSHOT, service_handler,
        schema=LOGI_CIRCLE_SERVICE_SNAPSHOT)

    hass.services.async_register(
        DOMAIN, SERVICE_LIVESTREAM_RECORD, service_handler,
        schema=LOGI_CIRCLE_SERVICE_RECORD)


class LogiCam(Camera):
    """An implementation of a Logi Circle camera."""

    def __init__(self, camera, device_info, ffmpeg):
        """Initialize Logi Circle camera."""
        super().__init__()
        self._camera = camera
        self._name = self._camera.name
        self._id = self._camera.id
        self._has_battery = self._camera.supports_feature('battery_level')
        self._ffmpeg = ffmpeg
        self._ffmpeg_arguments = device_info.data.get(
            CONF_CAMERAS).get(CONF_FFMPEG_ARGUMENTS)

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
            'model': '{} ({})'.format(self._camera.mount, self._camera.model),
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
        await stream.open_camera(
            live_stream, extra_cmd=self._ffmpeg_arguments)

        try:
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream,
                'multipart/x-mixed-replace;boundary=ffserver')
        finally:
            await stream.close(timeout=60)

    async def async_turn_off(self):
        """Disable streaming mode for this camera."""
        await self._camera.set_config('streaming_enabled', False)

    async def async_turn_on(self):
        """Enable streaming mode for this camera."""
        await self._camera.set_config('streaming_enabled', True)

    @property
    def should_poll(self):
        """Update the image periodically."""
        return True

    @property
    def is_on(self):
        """Return true if on."""
        return self._camera.is_connected and self._camera.streaming_enabled

    async def set_privacy_mode(self, value):
        """Set an configuration property for the target camera."""
        await self._camera.set_config('privacy_mode', value)

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
