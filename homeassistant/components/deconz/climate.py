"""
Support for deCONZ thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.deconz/
"""

from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_ON_OFF, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_ON, CONF_ALLOW_CLIP_SENSOR, DOMAIN as DECONZ_DOMAIN)
from .deconz_device import DeconzDevice

DEPENDENCIES = ['deconz']


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ climate devices.

    Thermostats are based on the same device class as sensors in deCONZ.
    """
    gateway = hass.data[DECONZ_DOMAIN]

    @callback
    def async_add_climate(sensors):
        """Add climate devices from deCONZ."""
        from pydeconz.sensor import THERMOSTAT
        entities = []
        allow_clip_sensor = config_entry.data.get(CONF_ALLOW_CLIP_SENSOR, True)
        for sensor in sensors:
            if sensor.type in THERMOSTAT and \
               not (not allow_clip_sensor and sensor.type.startswith('CLIP')):
                entities.append(DeconzThermostat(sensor, gateway))
        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(hass, 'deconz_new_sensor', async_add_climate))

    async_add_climate(gateway.api.sensors.values())


class DeconzThermostat(DeconzDevice, CoverDevice):
    """Representation of a deCONZ thermostat."""

    def __init__(self, device, gateway):
        """Set up thermostat device."""
        super().__init__(device, gateway)

        self._features = SUPPORT_TARGET_TEMPERATURE
        self._features |= SUPPORT_ON_OFF

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._features

    @property
    def is_on(self):
        """Return true if on."""
        return self._device.on

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {'on': True}
        await self._device.async_set_config(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {'on': False}
        await self._device.async_set_config(data)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.state

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._device.heatsetpoint

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        data = {}

        if ATTR_TEMPERATURE in kwargs:
            data['heatsetpoint'] = kwargs[ATTR_TEMPERATURE]

        await self._device.async_set_config(data)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 1
