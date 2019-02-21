"""
Support for mill wifi-enabled home heaters.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.mill/
"""

import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    DOMAIN, STATE_HEAT,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE,
    SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_PASSWORD, CONF_USERNAME,
    STATE_ON, STATE_OFF, TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['millheater==0.3.4']

_LOGGER = logging.getLogger(__name__)

ATTR_AWAY_TEMP = 'away_temp'
ATTR_COMFORT_TEMP = 'comfort_temp'
ATTR_ROOM_NAME = 'room_name'
ATTR_SLEEP_TEMP = 'sleep_temp'
MAX_TEMP = 35
MIN_TEMP = 5
SERVICE_SET_ROOM_TEMP = 'mill_set_room_temperature'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_FAN_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

SET_ROOM_TEMP_SCHEMA = vol.Schema({
    vol.Required(ATTR_ROOM_NAME): cv.string,
    vol.Optional(ATTR_AWAY_TEMP): cv.positive_int,
    vol.Optional(ATTR_COMFORT_TEMP): cv.positive_int,
    vol.Optional(ATTR_SLEEP_TEMP): cv.positive_int,
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

    await mill_data_connection.find_all_heaters()

    dev = []
    for heater in mill_data_connection.heaters.values():
        dev.append(MillHeater(heater, mill_data_connection))
    async_add_entities(dev)

    async def set_room_temp(service):
        """Set room temp."""
        room_name = service.data.get(ATTR_ROOM_NAME)
        sleep_temp = service.data.get(ATTR_SLEEP_TEMP)
        comfort_temp = service.data.get(ATTR_COMFORT_TEMP)
        away_temp = service.data.get(ATTR_AWAY_TEMP)
        await mill_data_connection.set_room_temperatures_by_name(room_name,
                                                                 sleep_temp,
                                                                 comfort_temp,
                                                                 away_temp)

    hass.services.async_register(DOMAIN, SERVICE_SET_ROOM_TEMP,
                                 set_room_temp, schema=SET_ROOM_TEMP_SCHEMA)


class MillHeater(ClimateDevice):
    """Representation of a Mill Thermostat device."""

    def __init__(self, heater, mill_data_connection):
        """Initialize the thermostat."""
        self._heater = heater
        self._conn = mill_data_connection

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._heater.is_gen1:
            return SUPPORT_FLAGS
        return SUPPORT_FLAGS | SUPPORT_ON_OFF | SUPPORT_OPERATION_MODE

    @property
    def available(self):
        """Return True if entity is available."""
        return self._heater.available

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.device_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._heater.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        res = {
            "open_window": self._heater.open_window,
            "heating": self._heater.is_heating,
            "controlled_by_tibber": self._heater.tibber_control,
            "heater_generation": 1 if self._heater.is_gen1 else 2,
        }
        if self._heater.room:
            res['room'] = self._heater.room.name
            res['avg_room_temp'] = self._heater.room.avg_temp
        else:
            res['room'] = "Independent device"
        return res

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
        if self._heater.is_gen1:
            return True
        return self._heater.power_status == 1

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def current_operation(self):
        """Return current operation."""
        return STATE_HEAT if self.is_on else STATE_OFF

    @property
    def operation_list(self):
        """List of available operation modes."""
        if self._heater.is_gen1:
            return None
        return [STATE_HEAT, STATE_OFF]

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

    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode == STATE_HEAT:
            await self.async_turn_on()
        elif operation_mode == STATE_OFF and not self._heater.is_gen1:
            await self.async_turn_off()
        else:
            _LOGGER.error("Unrecognized operation mode: %s", operation_mode)
