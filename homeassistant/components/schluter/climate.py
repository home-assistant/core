"""Support for Schluter thermostats."""
from datetime import timedelta
import logging

from requests import RequestException
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, TEMP_CELSIUS

from . import DATA_SCHLUTER, DOMAIN as SCHLUTER_DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Schluter thermostats."""
    data = hass.data[DATA_SCHLUTER]
    devices = []
    temp_unit = hass.config.units.temperature_unit

    for thermostat in data.thermostats:
        devices.append(SchluterThermostat(thermostat, temp_unit, data))

    async_add_entities(devices, True)


class SchluterThermostat(ClimateDevice):
    """Representation of a Schluter thermostat."""

    def __init__(self, device, temp_unit, data):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.device = device
        self.data = data

        # Set the default supported features
        self._support_flags = SUPPORT_TARGET_TEMPERATURE

        # data attributes
        self._serial_number = None
        self._group = None
        self._name = None
        self._target_temperature = None
        self._temperature = None
        self._temperature_scale = None
        self._is_heating = None
        self._action = None
        self._min_temperature = None
        self._max_temperature = None

    @property
    def should_poll(self):
        """Return if platform should poll."""
        return True

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self.device.serial_number

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(SCHLUTER_DOMAIN, self.device.serial_number)},
            "name": self.device.name,
            "manufacturer": "Schluter",
            "model": "Thermostat",
            "sw_version": self.device.sw_version,
        }

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, idle."""
        return HVAC_MODE_HEAT if self._is_heating else HVAC_MODE_OFF

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = None
        temp = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Setting thermostat temperature: %s", temp)

        try:
            if temp is not None:
                self.device.target = temp
                self.data.set_thermostat_temp(self._serial_number, temp)
        except RequestException as ex:
            _LOGGER.error("An error occurred while setting temperature: %s", ex)
            self.schedule_update_ha_state(True)

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return None

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        # No Fan available
        return None

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return None

    @property
    def min_temp(self):
        """Identify min_temp in Schluter API."""
        return self._min_temperature

    @property
    def max_temp(self):
        """Identify max_temp in Schluter API."""
        return self._max_temperature

    async def async_update(self):
        """Cache value from py-schluter."""
        await self.data.coordinator.async_request_refresh()
        self._serial_number = self.device.serial_number
        self._group = self.device.group_name
        self._name = self.device.name
        self._min_temperature = self.device.min_temp
        self._max_temperature = self.device.max_temp
        self._temperature_scale = TEMP_CELSIUS
        self._temperature = self.device.temperature
        self._is_heating = self.device.is_heating
        self._target_temperature = self.device.set_point_temp
