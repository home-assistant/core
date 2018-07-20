"""
Support for Chinese wifi thermostats (Floureon, Beok, Beca Energy)

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.broadlink/
"""
import asyncio
import json
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    DOMAIN, ClimateDevice,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, PLATFORM_SCHEMA,
    STATE_MANUAL, STATE_IDLE, STATE_AUTO)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE,
    CONF_NAME, CONF_HOST, CONF_MAC)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['broadlink==0.9.0', 'BroadlinkWifiThermostat==1.0.1']

DEFAULT_NAME = 'broadlink'
POWER_ON = 1
POWER_OFF = 0
AUTO = 1
MANUAL = 0
CONF_MODE_LIST = 'modes'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_ADVANCED_CONFIG = 'advanced_config'
CONF_SCHEDULE_WEEKDAY = 'schedule_week_day'
CONF_SCHEDULE_WEEKEND = 'schedule_week_end'
CONF_WEEKDAY = "weekday"
CONF_WEEKEND = "weekend"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MIN_TEMP, default=5): cv.positive_int,
    vol.Optional(CONF_MAX_TEMP, default=35): cv.positive_int,
    vol.Optional(CONF_ADVANCED_CONFIG,
                 default='{"loop_mode": 0, '
                         '"sen": 0, '
                         '"osv": 42, '
                         '"dif": 2, '
                         '"svh": 35, '
                         '"svl": 5, '
                         '"adj": 0, '
                         '"fre": 1, '
                         '"pon": 0}'): cv.string,
    vol.Optional(CONF_SCHEDULE_WEEKDAY,
                 default='[{"start_hour":6, '
                         '"start_minute":30, '
                         '"temp":20}, '
                         '{"start_hour":9, '
                         '"start_minute":0, '
                         '"temp":17}, '
                         '{"start_hour":12, '
                         '"start_minute":0, '
                         '"temp":20}, '
                         '{"start_hour":14, '
                         '"start_minute":0, '
                         '"temp":17}, '
                         '{"start_hour":18, '
                         '"start_minute":0, '
                         '"temp":20}, '
                         '{"start_hour":22, '
                         '"start_minute":30, '
                         '"temp":17}]'): cv.string,
    vol.Optional(CONF_SCHEDULE_WEEKEND,
                 default='[{"start_hour":8, '
                         '"start_minute":30, '
                         '"temp":20}, '
                         '{"start_hour":23, '
                         '"start_minute":0, '
                         '"temp":17}]'): cv.string
})

SET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required(CONF_WEEKDAY,
                 default='[{'
                         '"start_hour":6, '
                         '"start_minute":30, '
                         '"temp":20}, '
                         '{"start_hour":9, '
                         '"start_minute":0, '
                         '"temp":17}, '
                         '{"start_hour":12, '
                         '"start_minute":0, '
                         '"temp":20}, '
                         '{"start_hour":14, '
                         '"start_minute":0, '
                         '"temp":17}, '
                         '{"start_hour":18, '
                         '"start_minute":0, '
                         '"temp":20}, '
                         '{"start_hour":22, '
                         '"start_minute":30, '
                         '"temp":17}]'): cv.string,
    vol.Required(CONF_WEEKEND,
                 default='[{"start_hour":8, '
                         '"start_minute":30, '
                         '"temp":20}, '
                         '{"start_hour":23, '
                         '"start_minute":0, '
                         '"temp":17}]'): cv.string
})

SET_ADVANCED_CONF_SCHEMA = vol.Schema({
    vol.Required(CONF_ADVANCED_CONFIG,
                 default='{"loop_mode": 0, '
                         '"sen": 0, '
                         '"osv": 42, '
                         '"dif": 2, '
                         '"svh": 35, '
                         '"svl": 5, '
                         '"adj": 0, '
                         '"fre": 1, '
                         '"pon": 0}'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the broadlink thermostat platform."""
    import BroadlinkWifiThermostat
    wifi_thermostat = BroadlinkWifiThermostat.\
        Thermostat(config[CONF_MAC],
                   config[CONF_HOST],
                   config[CONF_NAME],
                   config[CONF_ADVANCED_CONFIG],
                   config[CONF_SCHEDULE_WEEKDAY],
                   config[CONF_SCHEDULE_WEEKDAY],
                   config[CONF_MIN_TEMP],
                   config[CONF_MAX_TEMP],
                   STATE_IDLE,
                   STATE_MANUAL,
                   STATE_AUTO)

    add_devices([BroadlinkThermostat(wifi_thermostat)], True)

    @asyncio.coroutine
    def handle_set_schedule(service):
        """Handle data for the set_schedule service call."""
        schedule_wd = service.data.get(CONF_WEEKDAY)
        schedule_we = service.data.get(CONF_WEEKEND)
        wifi_thermostat.set_schedule(
            {CONF_WEEKDAY:
             json.loads(schedule_wd.replace("'", '"')),
             CONF_WEEKEND:
             json.loads(schedule_we.replace("'", '"'))})

    hass.services.register(DOMAIN,
                           'set_schedule',
                           handle_set_schedule,
                           schema=SET_SCHEDULE_SCHEMA)

    @asyncio.coroutine
    def handle_set_advanced_conf(service):
        """Handle data for the set_advanced_conf service call."""
        advanced_conf = service.data.get(CONF_ADVANCED_CONFIG)
        wifi_thermostat.set_advanced_config(
            json.loads(advanced_conf.replace("'", '"')))

    hass.services.register(DOMAIN,
                           'set_advanced_conf',
                           handle_set_advanced_conf,
                           schema=SET_ADVANCED_CONF_SCHEMA)

    _LOGGER.debug("Wifi Thermostat: Component successfully added !")


class BroadlinkThermostat(ClimateDevice):
    """Representation of a Broadlink Thermostat device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._device.current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._device.max_temp

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._device.min_temp

    @property
    def current_operation(self):
        """Return current operation."""
        return self._device.current_operation

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [STATE_AUTO, STATE_IDLE, STATE_MANUAL]

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_temperature(kwargs.get(ATTR_TEMPERATURE))
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._device.set_operation_mode(operation_mode)
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn heater toggleable device on."""
        self._device.power_on_off(STATE_MANUAL)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn heater toggleable device off."""
        self._device.power_on_off(STATE_IDLE)
        self.schedule_update_ha_state()

    def set_advance_config(self, config_json):
        """Set the thermostat advanced config"""
        self._device.set_advanced_config(json.loads(config_json))
        self.schedule_update_ha_state()

    def set_schedule(self, schedule_json):
        """Set the thermostat schedule"""
        self._device.set_schedule(json.loads(schedule_json))
        self.schedule_update_ha_state()

    def update(self):
        """Update component data"""
        self._device.read_status()
