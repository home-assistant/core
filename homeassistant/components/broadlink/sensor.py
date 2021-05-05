"""Support for Broadlink sensors."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_HOST, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .helpers import import_device

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "temperature": ("Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE),
    "air_quality": ("Air Quality", None, None),
    "humidity": ("Humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY),
    "light": ("Light", None, DEVICE_CLASS_ILLUMINANCE),
    "noise": ("Noise", None, None),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string}, extra=vol.ALLOW_EXTRA
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the device and discontinue platform.

    This is for backward compatibility.
    Do not use this method.
    """
    import_device(hass, config[CONF_HOST])
    _LOGGER.warning(
        "The sensor platform is deprecated, please remove it from your configuration"
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink sensor."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    sensor_data = device.update_manager.coordinator.data
    sensors = [
        BroadlinkSensor(device, monitored_condition)
        for monitored_condition in sensor_data
        if sensor_data[monitored_condition] != 0 or device.api.type == "A1"
    ]
    async_add_entities(sensors)


class BroadlinkSensor(SensorEntity):
    """Representation of a Broadlink sensor."""

    def __init__(self, device, monitored_condition):
        """Initialize the sensor."""
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._monitored_condition = monitored_condition
        self._state = self._coordinator.data[monitored_condition]

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._device.unique_id}-{self._monitored_condition}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device.name} {SENSOR_TYPES[self._monitored_condition][0]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if the sensor is available."""
        return self._device.update_manager.available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return SENSOR_TYPES[self._monitored_condition][1]

    @property
    def should_poll(self):
        """Return True if the sensor has to be polled for state."""
        return False

    @property
    def device_class(self):
        """Return device class."""
        return SENSOR_TYPES[self._monitored_condition][2]

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            self._state = self._coordinator.data[self._monitored_condition]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the sensor is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
