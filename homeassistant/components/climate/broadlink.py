"""
Support for Chinese wifi thermostats (Floureon, Beok, Beca Energy).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.broadlink/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    DOMAIN, ClimateDevice,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_AWAY_MODE,
    PLATFORM_SCHEMA, STATE_HEAT, STATE_OFF, STATE_AUTO)
from homeassistant.const import (
    ATTR_TEMPERATURE, PRECISION_HALVES, TEMP_CELSIUS,
    CONF_FRIENDLY_NAME, CONF_HOST, CONF_MAC, ATTR_ENTITY_ID)
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['broadlink==0.9.0', 'BroadlinkWifiThermostat==2.3.0']

DEFAULT_NAME = 'broadlink'

CONF_EXTERNAL_TEMP = 'external_temp'
CONF_AWAY_TEMP = 'away_temp'

ATTR_LOOP_MODE = 'loop_mode'
ATTR_SEN = 'sen'
ATTR_OSV = 'osv'
ATTR_DIF = 'dif'
ATTR_SVH = 'svh'
ATTR_SVL = 'svl'
ATTR_ADJ = 'adj'
ATTR_FRE = 'freeze'
ATTR_PON = 'pon'

ATTR_WEEK_START_1 = 'week_start_1'
ATTR_WEEK_STOP_1 = 'week_stop_1'
ATTR_WEEK_START_2 = 'week_start_2'
ATTR_WEEK_STOP_2 = 'week_stop_2'
ATTR_WEEK_START_3 = 'week_start_3'
ATTR_WEEK_STOP_3 = 'week_stop_3'

ATTR_WEEKEND_START = 'weekend_start'
ATTR_WEEKEND_STOP = 'weekend_stop'
ATTR_AWAY_TEMP = 'away_temp'
ATTR_HOME_TEMP = 'home_temp'

SERVICE_SET_SCHEDULE = 'broadlink_set_schedule'
SERVICE_SET_ADVANCED_CONF = 'broadlink_set_advanced_conf'

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_EXTERNAL_TEMP, default=False): cv.boolean,
    vol.Optional(CONF_AWAY_TEMP, default=12): vol.Coerce(float),
    vol.Optional(ATTR_LOOP_MODE, default=0): vol.Coerce(int),
    vol.Optional(ATTR_SEN, default=0): vol.Coerce(int),
    vol.Optional(ATTR_OSV, default=42): vol.Coerce(int),
    vol.Optional(ATTR_DIF, default=2): vol.Coerce(int),
    vol.Optional(ATTR_SVH, default=35): vol.Coerce(int),
    vol.Optional(ATTR_SVL, default=5): vol.Coerce(int),
    vol.Optional(ATTR_ADJ, default=0.1): vol.Coerce(float),
    vol.Optional(ATTR_FRE, default=0): vol.Coerce(int),
    vol.Optional(ATTR_PON, default=0): vol.Coerce(int),
    vol.Optional(ATTR_WEEK_START_1): cv.time,
    vol.Optional(ATTR_WEEK_STOP_1): cv.time,
    vol.Optional(ATTR_WEEK_START_2): cv.time,
    vol.Optional(ATTR_WEEK_STOP_2): cv.time,
    vol.Optional(ATTR_WEEK_START_3): cv.time,
    vol.Optional(ATTR_WEEK_STOP_3): cv.time,
    vol.Optional(ATTR_WEEKEND_START): cv.time,
    vol.Optional(ATTR_WEEKEND_STOP): cv.time,
    vol.Optional(ATTR_HOME_TEMP): vol.Coerce(float),
    vol.Optional(ATTR_AWAY_TEMP): vol.Coerce(float)
})

SET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_WEEK_START_1): cv.time,
    vol.Required(ATTR_WEEK_STOP_1): cv.time,
    vol.Required(ATTR_WEEK_START_2): cv.time,
    vol.Required(ATTR_WEEK_STOP_2): cv.time,
    vol.Required(ATTR_WEEK_START_3): cv.time,
    vol.Required(ATTR_WEEK_STOP_3): cv.time,
    vol.Required(ATTR_WEEKEND_START): cv.time,
    vol.Required(ATTR_WEEKEND_STOP): cv.time,
    vol.Required(ATTR_HOME_TEMP): vol.Coerce(float),
    vol.Required(ATTR_AWAY_TEMP): vol.Coerce(float)
})

SET_ADVANCED_CONF_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_LOOP_MODE, default=0): vol.Coerce(int),
    vol.Required(ATTR_SEN, default=0): vol.Coerce(int),
    vol.Required(ATTR_OSV, default=42): vol.Coerce(int),
    vol.Required(ATTR_DIF, default=2): vol.Coerce(int),
    vol.Required(ATTR_SVH, default=35): vol.Coerce(int),
    vol.Required(ATTR_SVL, default=5): vol.Coerce(int),
    vol.Required(ATTR_ADJ, default=0.1): vol.Coerce(float),
    vol.Required(ATTR_FRE, default=0): vol.Coerce(int),
    vol.Required(ATTR_PON, default=0): vol.Coerce(int)
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, async_add_entities,
                   discovery_info=None):
    """Set up the broadlink thermostat platform."""
    import BroadlinkWifiThermostat
    wifi_thermostat = BroadlinkWifiThermostat.\
        Thermostat(config[CONF_MAC],
                   config[CONF_HOST],
                   config[CONF_FRIENDLY_NAME],
                   config[CONF_EXTERNAL_TEMP],
                   config[CONF_AWAY_TEMP])

    thermostats = [BroadlinkThermostat(wifi_thermostat)]

    async_add_entities(thermostats, True)

    def set_schedule(service):
        """Handle data for the set_schedule service call."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        if entity_id:
            target_thermostats = [device for device in thermostats
                                  if device.entity_id in entity_id]
        else:
            target_thermostats = thermostats

        week_start_1 = service.data.get(ATTR_WEEK_START_1)
        week_stop_1 = service.data.get(ATTR_WEEK_STOP_1)
        week_start_2 = service.data.get(ATTR_WEEK_START_2)
        week_stop_2 = service.data.get(ATTR_WEEK_STOP_2)
        week_start_3 = service.data.get(ATTR_WEEK_START_3)
        week_stop_3 = service.data.get(ATTR_WEEK_STOP_3)

        weekend_start = service.data.get(ATTR_WEEKEND_START)
        weekend_stop = service.data.get(ATTR_WEEKEND_STOP)
        away_temp = service.data.get(ATTR_AWAY_TEMP)
        home_temp = service.data.get(ATTR_HOME_TEMP)

        for thermostat in target_thermostats:
            thermostat.set_schedule(week_start_1, week_stop_1,
                                    week_start_2, week_stop_2,
                                    week_start_3, week_stop_3,
                                    weekend_start, weekend_stop,
                                    away_temp, home_temp)

    hass.services.register(DOMAIN, SERVICE_SET_SCHEDULE,
                           set_schedule, schema=SET_SCHEDULE_SCHEMA)

    def set_advanced_conf(service):
        """Handle data for the set_advanced_conf service call."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        if entity_id:
            target_thermostats = [device for device in thermostats
                                  if device.entity_id in entity_id]
        else:
            target_thermostats = thermostats

        loop_mode = service.data.get(ATTR_LOOP_MODE)
        sen = service.data.get(ATTR_SEN)
        osv = service.data.get(ATTR_OSV)
        dif = service.data.get(ATTR_DIF)
        svh = service.data.get(ATTR_SVH)
        svl = service.data.get(ATTR_SVL)
        adj = service.data.get(ATTR_ADJ)
        fre = service.data.get(ATTR_FRE)
        pon = service.data.get(ATTR_PON)
        target_thermostats.set_advanced_config(loop_mode, sen, osv,
                                               dif, svh, svl, adj, fre, pon)

    hass.services.register(DOMAIN, SERVICE_SET_ADVANCED_CONF,
                           set_advanced_conf, schema=SET_SCHEDULE_SCHEMA)


class BroadlinkThermostat(ClimateDevice):
    """Representation of a Broadlink Thermostat device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device
        device.set_time()

    @property
    def state(self):
        """Return climate state."""
        return self._device.state

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE \
                                          | SUPPORT_AWAY_MODE

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
    def current_operation(self):
        """Return current operation."""
        return self._device.current_operation

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [STATE_AUTO, STATE_HEAT, STATE_OFF]

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._device.away

    @property
    def is_on(self):
        """Return true if the device is on."""
        return not self._device.current_operation == STATE_OFF

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_temperature(kwargs.get(ATTR_TEMPERATURE))

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._device.set_operation_mode(operation_mode)

    def set_schedule(self, week_start_1, week_stop_1,
                     week_start_2, week_stop_2,
                     week_start_3, week_stop_3,
                     weekend_start, weekend_stop,
                     away_temp, home_temp):
        """Set automatic schedule."""
        self._device.set_schedule(week_start_1, week_stop_1,
                                  week_start_2, week_stop_2,
                                  week_start_3, week_stop_3,
                                  weekend_start, weekend_stop,
                                  away_temp, home_temp)

    def set_advanced_config(self, loop_mode, sen, osv,
                            dif, svh, svl, adj, fre, pon):
        """Set advanced configuration."""
        self._device.set_advanced_config(self, loop_mode, sen, osv,
                                         dif, svh, svl, adj, fre, pon)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._device.set_away(True)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._device.set_away(False)

    def update(self):
        """Update component data."""
        self._device.read_status()
