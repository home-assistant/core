"""
Support for mill wifi-enabled home heaters.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.mill/
"""

import logging

import voluptuous as vol
from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE, SUPPORT_ON_OFF)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_PASSWORD, CONF_USERNAME,
    STATE_ON, STATE_OFF, TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['millheater==0.1.2']

_LOGGER = logging.getLogger(__name__)

MAX_TEMP = 35
MIN_TEMP = 5
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_FAN_MODE | SUPPORT_ON_OFF)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Mill heater."""
    from mill import Mill
    mill_data_connection = Mill(config[CONF_USERNAME],
                                config[CONF_PASSWORD],
                                websession=async_get_clientsession(hass))
    if not await mill_data_connection.connect():
        _LOGGER.error("Failed to connect to Mill")
        return

    await mill_data_connection.update_heaters()

    dev = []
    for heater in mill_data_connection.heaters.values():
        dev.append(MillHeater(heater, mill_data_connection))
    async_add_entities(dev)


class MillHeater(ClimateDevice):
    """Representation of a Mill Thermostat device."""

    def __init__(self, heater, mill_data_connection):
        """Initialize the thermostat."""
        self._heater = heater
        self._conn = mill_data_connection

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self):
        """Return True if entity is available."""
        return self._heater.device_status == 0  # weird api choice

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.device_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._heater.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._heater.set_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._heater.current_temp

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return STATE_ON if self._heater.fan_status == 1 else STATE_OFF

    @property
    def fan_list(self):
        """List of available fan modes."""
        return [STATE_ON, STATE_OFF]

    @property
    def is_on(self):
        """Return true if heater is on."""
        return self._heater.power_status == 1

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._conn.set_heater_temp(self._heater.device_id,
                                         int(temperature))

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        fan_status = 1 if fan_mode == STATE_ON else 0
        await self._conn.heater_control(self._heater.device_id,
                                        fan_status=fan_status)

    async def async_turn_on(self):
        """Turn Mill unit on."""
        await self._conn.heater_control(self._heater.device_id,
                                        power_status=1)

    async def async_turn_off(self):
        """Turn Mill unit off."""
        await self._conn.heater_control(self._heater.device_id,
                                        power_status=0)

    async def async_update(self):
        """Retrieve latest state."""
        self._heater = await self._conn.update_device(self._heater.device_id)
