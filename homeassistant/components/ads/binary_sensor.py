"""Support for ADS binary sensors."""
import logging
import asyncio
import async_timeout

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import CONF_ADS_VAR, DATA_ADS

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ADS binary sensor'
DEPENDENCIES = ['ads']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    ads_var = config.get(CONF_ADS_VAR)
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    ads_sensor = AdsBinarySensor(ads_hub, name, ads_var, device_class)
    add_entities([ads_sensor])


class AdsBinarySensor(BinarySensorDevice):
    """Representation of ADS binary sensors."""

    def __init__(self, ads_hub, name, ads_var, device_class):
        """Initialize ADS binary sensor."""
        self._name = name
        self._unique_id = ads_var
        self._state = None
        self._device_class = device_class or 'moving'
        self._ads_hub = ads_hub
        self.ads_var = ads_var
        self._event = None

    async def async_added_to_hass(self):
        """Register device notification."""
        def update(name, value):
            """Handle device notifications."""
            _LOGGER.debug('Variable %s changed its value to %d', name, value)
            self._state = value
            asyncio.run_coroutine_threadsafe(async_event_set(), self.hass.loop)
            self.schedule_update_ha_state()

        async def async_event_set():
            """Set event in async context."""
            self._event.set()

        self._event = asyncio.Event()

        await self.hass.async_add_executor_job(
            self._ads_hub.add_device_notification,
            self.ads_var, self._ads_hub.PLCTYPE_BOOL, update)
        try:
            with async_timeout.timeout(10):
                await self._event.wait()
        except asyncio.TimeoutError:
            _LOGGER.debug('Variable %s: Timeout during first update',
                          self.ads_var)

    @property
    def name(self):
        """Return the default name of the binary sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique identifier for this entity."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_on(self):
        """Return if the binary sensor is on."""
        return self._state

    @property
    def should_poll(self):
        """Return False because entity pushes its state to HA."""
        return False

    @property
    def available(self):
        """Return False if state has not been updated yet."""
        return self._state is not None
