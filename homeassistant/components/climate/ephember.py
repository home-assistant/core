"""
Support for the EPH Controls Ember themostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.ephember/
"""
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, STATE_HEAT, STATE_OFF,
    STATE_AUTO, SUPPORT_AUX_HEAT, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    TEMP_CELSIUS, CONF_USERNAME, CONF_PASSWORD, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyephember==0.2.0']

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
SCAN_INTERVAL = timedelta(seconds=120)

OPERATION_LIST = [STATE_AUTO, STATE_HEAT, STATE_OFF]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

EPH_TO_HA_STATE = {
    'AUTO': STATE_AUTO,
    'ON': STATE_HEAT,
    'OFF': STATE_OFF
}

HA_STATE_TO_EPH = {value: key for key, value in EPH_TO_HA_STATE.items()}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ephember thermostat."""
    from pyephember.pyephember import EphEmber

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        ember = EphEmber(username, password)
        zones = ember.get_zones()
        for zone in zones:
            add_entities([EphEmberThermostat(ember, zone)])
    except RuntimeError:
        _LOGGER.error("Cannot connect to EphEmber")
        return

    return


class EphEmberThermostat(ClimateDevice):
    """Representation of a HeatmiserV3 thermostat."""

    def __init__(self, ember, zone):
        """Initialize the thermostat."""
        self._ember = ember
        self._zone_name = zone['name']
        self._zone = zone
        self._hot_water = zone['isHotWater']

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._hot_water:
            return SUPPORT_AUX_HEAT | SUPPORT_OPERATION_MODE

        return (SUPPORT_TARGET_TEMPERATURE |
                SUPPORT_AUX_HEAT |
                SUPPORT_OPERATION_MODE)

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._zone_name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._zone['currentTemperature']

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._zone['targetTemperature']

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        if self._hot_water:
            return None

        return 1

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        attributes = {
            'currently_active': self._zone['isCurrentlyActive']
        }
        return attributes

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self._ember.get_zone_mode(self._zone_name)
        return self.map_mode_eph_hass(mode)

    @property
    def operation_list(self):
        """Return the supported operations."""
        return OPERATION_LIST

    def set_operation_mode(self, operation_mode):
        """Set the operation mode."""
        mode = self.map_mode_hass_eph(operation_mode)
        if mode is not None:
            self._ember.set_mode_by_name(self._zone_name, mode)
        else:
            _LOGGER.error("Invalid operation mode provided %s", operation_mode)

    @property
    def is_on(self):
        """Return current state."""
        if self._zone['isCurrentlyActive']:
            return True

        return None

    @property
    def is_aux_heat_on(self):
        """Return true if aux heater."""
        return self._zone['isBoostActive']

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._ember.activate_boost_by_name(
            self._zone_name, self._zone['targetTemperature'])

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._ember.deactivate_boost_by_name(self._zone_name)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if self._hot_water:
            return

        if temperature == self.target_temperature:
            return

        if temperature > self.max_temp or temperature < self.min_temp:
            return

        self._ember.set_target_temperture_by_name(self._zone_name,
                                                  int(temperature))

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # Hot water temp doesn't support being changed
        if self._hot_water:
            return self._zone['targetTemperature']

        return 5

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._hot_water:
            return self._zone['targetTemperature']

        return 35

    def update(self):
        """Get the latest data."""
        self._zone = self._ember.get_zone(self._zone_name)

    @staticmethod
    def map_mode_hass_eph(operation_mode):
        """Map from home assistant mode to eph mode."""
        from pyephember.pyephember import ZoneMode
        return getattr(ZoneMode, HA_STATE_TO_EPH.get(operation_mode), None)

    @staticmethod
    def map_mode_eph_hass(operation_mode):
        """Map from eph mode to home assistant mode."""
        return EPH_TO_HA_STATE.get(operation_mode.name, STATE_AUTO)
