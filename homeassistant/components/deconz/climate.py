"""Support for deCONZ climate devices."""
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_ON_OFF, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_OFFSET, ATTR_VALVE, CONF_ALLOW_CLIP_SENSOR,
    DOMAIN as DECONZ_DOMAIN, NEW_SENSOR)
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
        async_dispatcher_connect(hass, NEW_SENSOR, async_add_climate))

    async_add_climate(gateway.api.sensors.values())


class DeconzThermostat(DeconzDevice, ClimateDevice):
    """Representation of a deCONZ thermostat."""

    def __init__(self, device, gateway):
        """Set up thermostat device."""
        super().__init__(device, gateway)

        self._features = SUPPORT_ON_OFF
        self._features |= SUPPORT_TARGET_TEMPERATURE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._features

    @property
    def is_on(self):
        """Return true if on."""
        return self._device.on

    async def async_turn_on(self):
        """Turn on switch."""
        data = {'mode': 'auto'}
        await self._device.async_set_config(data)

    async def async_turn_off(self):
        """Turn off switch."""
        data = {'mode': 'off'}
        await self._device.async_set_config(data)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._device.heatsetpoint

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        data = {}

        if ATTR_TEMPERATURE in kwargs:
            data['heatsetpoint'] = kwargs[ATTR_TEMPERATURE] * 100

        await self._device.async_set_config(data)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the thermostat."""
        attr = {}

        if self._device.battery:
            attr[ATTR_BATTERY_LEVEL] = self._device.battery

        if self._device.offset:
            attr[ATTR_OFFSET] = self._device.offset

        if self._device.valve is not None:
            attr[ATTR_VALVE] = self._device.valve

        return attr
