"""
This component provides support to the Logi Circle camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.logi/
"""
import logging
import os
import asyncio
from tempfile import NamedTemporaryFile

from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.components.logi import (
    DATA_LOGI, CONF_ATTRIBUTION)
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA, CAMERA_SERVICE_SCHEMA, SUPPORT_ON_OFF, ATTR_ENTITY_ID, ATTR_FILENAME, DOMAIN)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.const import ATTR_ATTRIBUTION, CONF_SCAN_INTERVAL

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEPENDENCIES = ['logi', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_MODE = 'logi_set_mode'
SERVICE_LIVESTREAM_SNAPSHOT = 'logi_livestream_snapshot'
SERVICE_DOWNLOAD_LIVESTREAM = 'logi_download_livestream'
DATA_KEY = 'camera.logi'

STREAMING_MODE_KEY = 'streaming_mode'
PRIVACY_MODE_KEY = 'privacy_mode'
LED_MODE_KEY = 'led'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
        cv.time_period,
})

LOGI_SERVICE_SET_MODE = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required('mode'): cv.string,
    vol.Required('value'): cv.match_all
})

LOGI_SERVICE_SNAPSHOT = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template
})

LOGI_SERVICE_DOWNLOAD = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template,
    vol.Required('duration'): cv.positive_int
})


async def async_setup_platform(hass,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up a Logi Circle Camera."""
    devices = hass.data[DATA_LOGI]

    cameras = []
    for device in devices:
        cameras.append(LogiCam(hass, device, config))

    async_add_devices(cameras, True)

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
            if service.service == SERVICE_SET_MODE:
                await target_device.set_mode(**params)
            if service.service == SERVICE_LIVESTREAM_SNAPSHOT:
                await target_device.livestream_snapshot(**params)
            if service.service == SERVICE_DOWNLOAD_LIVESTREAM:
                await target_device.download_livestream(**params)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_MODE, service_handler,
        schema=LOGI_SERVICE_SET_MODE)

    hass.services.async_register(
        DOMAIN, SERVICE_LIVESTREAM_SNAPSHOT, service_handler,
        schema=LOGI_SERVICE_SNAPSHOT)

    hass.services.async_register(
        DOMAIN, SERVICE_DOWNLOAD_LIVESTREAM, service_handler,
        schema=LOGI_SERVICE_DOWNLOAD)

    return True


class LogiCam(Camera):
    """An implementation of a Logi Circle camera."""

    def __init__(self, hass, camera, device_info):
        """Initialize Logi camera."""
        super(LogiCam, self).__init__()
        self._camera = camera
        self._hass = hass
        self._name = self._camera.name
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device_info.get(CONF_FFMPEG_ARGUMENTS)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def supported_features(self):
        """Logi Circle camera's support turning on and off ("soft" switch)."""
        return SUPPORT_ON_OFF

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'firmware': self._camera.firmware,
            'model': self._camera.model,
            'model_type': self._camera.model_type,
            'timezone': self._camera.timezone,
            'ip_address': self._camera.ip_address,
            'mac_address': self._camera.mac_address,
            'plan': self._camera.plan_name
        }

    async def async_camera_image(self):
        """Return a still image from the camera."""
        if self._camera.node_id is not None:
            return await self._camera.get_snapshot_image()
        _LOGGER.warning(
            'Node ID missing for %s, image can not be retrieved.', self._name)

    async def async_turn_off(self):
        """Disable streaming mode for this camera."""
        await self._camera.set_streaming_mode('off')

    async def async_turn_on(self):
        """Enable streaming mode for this camera."""
        if self._camera.model == 'A1533':
            await self._camera.set_streaming_mode('on')
        else:
            await self._camera.set_streaming_mode('onAlert')

    @property
    def should_poll(self):
        """Update the image periodically."""
        return True

    async def set_mode(self, mode, value):
        """Sets an operation mode for the target camera."""
        if mode == STREAMING_MODE_KEY:
            await self._camera.set_streaming_mode(value)
        if mode == LED_MODE_KEY:
            await self._camera.set_led(value)
        if mode == PRIVACY_MODE_KEY:
            await self._camera.set_privacy_mode(value)

    async def download_livestream(self, filename, duration):
        """Downloads a recording from the livestream and writes to disk."""
        # Render filename from template
        filename.hass = self._hass
        stream_file = filename.async_render(
            variables={ATTR_ENTITY_ID: self.entity_id})

        # Work out when to stop downloading live stream
        recording_end_time = datetime.now() + timedelta(seconds=duration)

        # Start downloading
        live_stream = self._camera.live_stream
        while recording_end_time > datetime.now():
            await live_stream.get_segment(filename=stream_file, append=True)

    async def livestream_snapshot(self, filename):
        """Returns the first frame for the camera's livestream and writes to disk."""
        # Render filename from template.
        filename.hass = self._hass
        snapshot_file = filename.async_render(
            variables={ATTR_ENTITY_ID: self.entity_id})

        # Get temp file to store live stream segment.
        temp_file = NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_file.close()
        temp_file_path = temp_file.name

        # Get 1st segment from livestream and write to disk
        live_stream = self._camera.live_stream
        await live_stream.get_segment(filename=temp_file_path)

        # Extract image from 1st frame of livestream segment
        from haffmpeg import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        image = await asyncio.shield(ffmpeg.get_image(
            temp_file_path, output_format=IMAGE_JPEG,
            extra_cmd=self._ffmpeg_arguments), loop=self.hass.loop)

        def _write_image(to_file, image_data):
            """Executor helper to write image."""
            with open(to_file, 'wb') as img_file:
                img_file.write(image_data)

        try:
            await self._hass.async_add_executor_job(
                _write_image, snapshot_file, image)
        except OSError as err:
            _LOGGER.error("Can't write image to file: %s", err)
        finally:
            os.remove(temp_file_path)

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        await self._camera.update()
