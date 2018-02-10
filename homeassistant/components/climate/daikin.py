"""
Support for the Daikin HVAC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.daikin/
"""
import logging
import re

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_FAN_MODE, ATTR_OPERATION_MODE,
    ATTR_SWING_MODE, PLATFORM_SCHEMA, STATE_AUTO, STATE_COOL, STATE_DRY,
    STATE_FAN_ONLY, STATE_HEAT, STATE_OFF, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE, SUPPORT_TARGET_TEMPERATURE,
    ClimateDevice)
from homeassistant.components.daikin import (
    ATTR_INSIDE_TEMPERATURE, ATTR_OUTSIDE_TEMPERATURE, ATTR_TARGET_TEMPERATURE,
    daikin_api_setup)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, CONF_NAME, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pydaikin==0.4']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
})

HA_STATE_TO_DAIKIN = {
    STATE_FAN_ONLY: 'fan',
    STATE_DRY: 'dry',
    STATE_COOL: 'cool',
    STATE_HEAT: 'hot',
    STATE_AUTO: 'auto',
    STATE_OFF: 'off',
}

HA_ATTR_TO_DAIKIN = {
    ATTR_OPERATION_MODE: 'mode',
    ATTR_FAN_MODE: 'f_rate',
    ATTR_SWING_MODE: 'f_dir',
    ATTR_INSIDE_TEMPERATURE: 'htemp',
    ATTR_OUTSIDE_TEMPERATURE: 'otemp',
    ATTR_TARGET_TEMPERATURE: 'stemp'
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Daikin HVAC platform."""
    if discovery_info is not None:
        host = discovery_info.get('ip')
        name = None
        _LOGGER.debug("Discovered a Daikin AC on %s", host)
    else:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
        _LOGGER.debug("Added Daikin AC on %s", host)

    api = daikin_api_setup(hass, host, name)
    add_devices([DaikinClimate(api)], True)


class DaikinClimate(ClimateDevice):
    """Representation of a Daikin HVAC."""

    def __init__(self, api):
        """Initialize the climate device."""
        from pydaikin import appliance

        self._api = api
        self._force_refresh = False
        self._list = {
            ATTR_OPERATION_MODE: list(
                map(str.title, set(HA_STATE_TO_DAIKIN.values()))
            ),
            ATTR_FAN_MODE: list(
                map(
                    str.title,
                    appliance.daikin_values(HA_ATTR_TO_DAIKIN[ATTR_FAN_MODE])
                )
            ),
            ATTR_SWING_MODE: list(
                map(
                    str.title,
                    appliance.daikin_values(HA_ATTR_TO_DAIKIN[ATTR_SWING_MODE])
                )
            ),
        }

        self._supported_features = SUPPORT_TARGET_TEMPERATURE \
            | SUPPORT_OPERATION_MODE

        daikin_attr = HA_ATTR_TO_DAIKIN[ATTR_FAN_MODE]
        if self._api.device.values.get(daikin_attr) is not None:
            self._supported_features |= SUPPORT_FAN_MODE
        else:
            # even devices without support must have a default valid value
            self._api.device.values[daikin_attr] = 'A'

        daikin_attr = HA_ATTR_TO_DAIKIN[ATTR_SWING_MODE]
        if self._api.device.values.get(daikin_attr) is not None:
            self._supported_features |= SUPPORT_SWING_MODE
        else:
            # even devices without support must have a default valid value
            self._api.device.values[daikin_attr] = '0'

    def get(self, key):
        """Retrieve device settings from API library cache."""
        value = None
        cast_to_float = False

        if key in [ATTR_TEMPERATURE, ATTR_INSIDE_TEMPERATURE,
                   ATTR_CURRENT_TEMPERATURE]:
            key = ATTR_INSIDE_TEMPERATURE

        daikin_attr = HA_ATTR_TO_DAIKIN.get(key)

        if key == ATTR_INSIDE_TEMPERATURE:
            value = self._api.device.values.get(daikin_attr)
            cast_to_float = True
        elif key == ATTR_TARGET_TEMPERATURE:
            value = self._api.device.values.get(daikin_attr)
            cast_to_float = True
        elif key == ATTR_OUTSIDE_TEMPERATURE:
            value = self._api.device.values.get(daikin_attr)
            cast_to_float = True
        elif key == ATTR_FAN_MODE:
            value = self._api.device.represent(daikin_attr)[1].title()
        elif key == ATTR_SWING_MODE:
            value = self._api.device.represent(daikin_attr)[1].title()
        elif key == ATTR_OPERATION_MODE:
            # Daikin can return also internal states auto-1 or auto-7
            # and we need to translate them as AUTO
            value = re.sub(
                '[^a-z]',
                '',
                self._api.device.represent(daikin_attr)[1]
            ).title()

        if value is None:
            _LOGGER.error("Invalid value requested for key %s", key)
        else:
            if value == "-" or value == "--":
                value = None
            elif cast_to_float:
                try:
                    value = float(value)
                except ValueError:
                    value = None

        return value

    def set(self, settings):
        """Set device settings using API."""
        values = {}

        for attr in [ATTR_TEMPERATURE, ATTR_FAN_MODE, ATTR_SWING_MODE,
                     ATTR_OPERATION_MODE]:
            value = settings.get(attr)
            if value is None:
                continue

            daikin_attr = HA_ATTR_TO_DAIKIN.get(attr)
            if daikin_attr is not None:
                if value.title() in self._list[attr]:
                    values[daikin_attr] = value.lower()
                else:
                    _LOGGER.error("Invalid value %s for %s", attr, value)

            # temperature
            elif attr == ATTR_TEMPERATURE:
                try:
                    values['stemp'] = str(int(value))
                except ValueError:
                    _LOGGER.error("Invalid temperature %s", value)

        if values:
            self._force_refresh = True
            self._api.device.set(values)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._api.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.get(ATTR_CURRENT_TEMPERATURE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.get(ATTR_TARGET_TEMPERATURE)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        self.set(kwargs)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self.get(ATTR_OPERATION_MODE)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._list.get(ATTR_OPERATION_MODE)

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode."""
        self.set({ATTR_OPERATION_MODE: operation_mode})

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self.get(ATTR_FAN_MODE)

    def set_fan_mode(self, fan):
        """Set fan mode."""
        self.set({ATTR_FAN_MODE: fan})

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._list.get(ATTR_FAN_MODE)

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return self.get(ATTR_SWING_MODE)

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self.set({ATTR_SWING_MODE: swing_mode})

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._list.get(ATTR_SWING_MODE)

    def update(self):
        """Retrieve latest state."""
        self._api.update(no_throttle=self._force_refresh)
        self._force_refresh = False
