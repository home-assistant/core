"""
This component provides support to the Logi Circle camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.logi/
"""
import logging

from datetime import timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.components.logi import (
    DATA_LOGI, CONF_ATTRIBUTION)
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA, CAMERA_SERVICE_SCHEMA, SUPPORT_ON_OFF)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION, CONF_SCAN_INTERVAL

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEPENDENCIES = ['logi', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_MODE = 'set_mode'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
        cv.time_period,
})

LOGI_SERVICE_SCHEMA = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required('mode'): cv.string,
    vol.Required('value'): cv.boolean
})


async def async_setup_platform(hass,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up a Logi Circle Camera."""
    logi = hass.data[DATA_LOGI]

    cameras = []
    for camera in await logi.cameras:
        cameras.append(LogiCam(hass, camera, config))

    async_add_devices(cameras, True)

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
    def is_on(self):
        """Return true if connected and streaming."""
        return self._camera.is_connected and self._camera.is_streaming

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }
        attrs_to_check = ['firmware', 'model', 'timezone',
                          'ip_address', 'mac_address', 'plan_name']

        for attr in attrs_to_check:
            if getattr(self._camera, attr, None) is not None:
                attrs[attr] = getattr(self._camera, attr)

        return attrs

    async def async_camera_image(self):
        """Return a still image from the camera."""
        if self._camera.node_id is not None:
            return await self._camera.get_snapshot_image()
        _LOGGER.warning(
            'Node ID missing for %s, image can not be retrieved.', self._name)

    async def async_turn_off(self):
        """Disable streaming mode for this camera."""
        await self._camera.set_streaming_mode(False)

    async def async_turn_on(self):
        """Enable streaming mode for this camera."""
        await self._camera.set_streaming_mode(True)

    @property
    def should_poll(self):
        """Update the image periodically."""
        return True

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        await self._camera.update()
