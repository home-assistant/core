"""Support to the Logi Circle cameras."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.camera import (
    ATTR_ENTITY_ID, ATTR_FILENAME, CAMERA_SERVICE_SCHEMA,
    PLATFORM_SCHEMA, SUPPORT_ON_OFF, Camera)
from homeassistant.components.camera.const import DOMAIN
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_BATTERY_CHARGING, ATTR_BATTERY_LEVEL,
    CONF_SCAN_INTERVAL, STATE_OFF, STATE_ON)
from homeassistant.helpers import config_validation as cv

from . import ATTRIBUTION, DOMAIN as LOGI_CIRCLE_DOMAIN

DEPENDENCIES = ['logi_circle']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

SERVICE_SET_CONFIG = 'logi_circle_set_config'
SERVICE_LIVESTREAM_SNAPSHOT = 'logi_circle_livestream_snapshot'
SERVICE_LIVESTREAM_RECORD = 'logi_circle_livestream_record'
DATA_KEY = 'camera.logi_circle'

BATTERY_SAVING_MODE_KEY = 'BATTERY_SAVING'
PRIVACY_MODE_KEY = 'PRIVACY_MODE'
LED_MODE_KEY = 'LED'

ATTR_MODE = 'mode'
ATTR_VALUE = 'value'
ATTR_DURATION = 'duration'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
        cv.time_period,
})

LOGI_CIRCLE_SERVICE_SET_CONFIG = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_MODE): vol.In([BATTERY_SAVING_MODE_KEY, LED_MODE_KEY,
                                     PRIVACY_MODE_KEY]),
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
    """Set up a Logi Circle Camera."""
    devices = hass.data[LOGI_CIRCLE_DOMAIN]

    cameras = []
    for device in devices:
        cameras.append(LogiCam(device, config))

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
            if service.service == SERVICE_SET_CONFIG:
                await target_device.set_config(**params)
            if service.service == SERVICE_LIVESTREAM_SNAPSHOT:
                await target_device.livestream_snapshot(**params)
            if service.service == SERVICE_LIVESTREAM_RECORD:
                await target_device.download_livestream(**params)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CONFIG, service_handler,
        schema=LOGI_CIRCLE_SERVICE_SET_CONFIG)

    hass.services.async_register(
        DOMAIN, SERVICE_LIVESTREAM_SNAPSHOT, service_handler,
        schema=LOGI_CIRCLE_SERVICE_SNAPSHOT)

    hass.services.async_register(
        DOMAIN, SERVICE_LIVESTREAM_RECORD, service_handler,
        schema=LOGI_CIRCLE_SERVICE_RECORD)


class LogiCam(Camera):
    """An implementation of a Logi Circle camera."""

    def __init__(self, camera, device_info):
        """Initialize Logi Circle camera."""
        super().__init__()
        self._camera = camera
        self._name = self._camera.name
        self._id = self._camera.mac_address
        self._has_battery = self._camera.supports_feature('battery_level')

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
    def device_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'battery_saving_mode': (
                STATE_ON if self._camera.battery_saving else STATE_OFF),
            'ip_address': self._camera.ip_address,
            'microphone_gain': self._camera.microphone_gain
        }

        # Add battery attributes if camera is battery-powered
        if self._has_battery:
            state[ATTR_BATTERY_CHARGING] = self._camera.is_charging
            state[ATTR_BATTERY_LEVEL] = self._camera.battery_level

        return state

    async def async_camera_image(self):
        """Return a still image from the camera."""
        return await self._camera.get_snapshot_image()

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

    async def set_config(self, mode, value):
        """Set an configuration property for the target camera."""
        if mode == LED_MODE_KEY:
            await self._camera.set_led(value)
        if mode == PRIVACY_MODE_KEY:
            await self._camera.set_privacy_mode(value)
        if mode == BATTERY_SAVING_MODE_KEY:
            await self._camera.set_battery_saving_mode(value)

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

        asyncio.shield(self._camera.record_livestream(
            stream_file, timedelta(seconds=duration)), loop=self.hass.loop)

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

        asyncio.shield(self._camera.get_livestream_image(
            snapshot_file), loop=self.hass.loop)

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        await self._camera.update()
