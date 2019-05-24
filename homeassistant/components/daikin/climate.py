"""Support for the Daikin HVAC."""
import logging
import re

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_AWAY_MODE, ATTR_CURRENT_TEMPERATURE, ATTR_FAN_MODE,
    ATTR_OPERATION_MODE, ATTR_SWING_MODE, STATE_AUTO, STATE_COOL, STATE_DRY,
    STATE_FAN_ONLY, STATE_HEAT, SUPPORT_AWAY_MODE, SUPPORT_FAN_MODE,
    SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, CONF_NAME, STATE_OFF, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as DAIKIN_DOMAIN
from .const import (
    ATTR_INSIDE_TEMPERATURE, ATTR_OUTSIDE_TEMPERATURE, ATTR_TARGET_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

HA_STATE_TO_DAIKIN = {
    STATE_FAN_ONLY: 'fan',
    STATE_DRY: 'dry',
    STATE_COOL: 'cool',
    STATE_HEAT: 'hot',
    STATE_AUTO: 'auto',
    STATE_OFF: 'off',
}

DAIKIN_TO_HA_STATE = {
    'fan': STATE_FAN_ONLY,
    'dry': STATE_DRY,
    'cool': STATE_COOL,
    'hot': STATE_HEAT,
    'auto': STATE_AUTO,
    'off': STATE_OFF,
}

HA_ATTR_TO_DAIKIN = {
    ATTR_AWAY_MODE: 'en_hol',
    ATTR_OPERATION_MODE: 'mode',
    ATTR_FAN_MODE: 'f_rate',
    ATTR_SWING_MODE: 'f_dir',
    ATTR_INSIDE_TEMPERATURE: 'htemp',
    ATTR_OUTSIDE_TEMPERATURE: 'otemp',
    ATTR_TARGET_TEMPERATURE: 'stemp'
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the Daikin HVAC platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Daikin climate based on config_entry."""
    daikin_api = hass.data[DAIKIN_DOMAIN].get(entry.entry_id)
    async_add_entities([DaikinClimate(daikin_api)])


class DaikinClimate(ClimateDevice):
    """Representation of a Daikin HVAC."""

    def __init__(self, api):
        """Initialize the climate device."""
        from pydaikin import appliance

        self._api = api
        self._list = {
            ATTR_OPERATION_MODE: list(HA_STATE_TO_DAIKIN),
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

        self._supported_features = (SUPPORT_AWAY_MODE | SUPPORT_ON_OFF
                                    | SUPPORT_OPERATION_MODE
                                    | SUPPORT_TARGET_TEMPERATURE)

        if self._api.device.support_fan_mode:
            self._supported_features |= SUPPORT_FAN_MODE

        if self._api.device.support_swing_mode:
            self._supported_features |= SUPPORT_SWING_MODE

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
            daikin_mode = re.sub(
                '[^a-z]', '',
                self._api.device.represent(daikin_attr)[1])
            ha_mode = DAIKIN_TO_HA_STATE.get(daikin_mode)
            value = ha_mode

        if value is None:
            _LOGGER.error("Invalid value requested for key %s", key)
        else:
            if value in ("-", "--"):
                value = None
            elif cast_to_float:
                try:
                    value = float(value)
                except ValueError:
                    value = None

        return value

    async def _set(self, settings):
        """Set device settings using API."""
        values = {}

        for attr in [ATTR_TEMPERATURE, ATTR_FAN_MODE, ATTR_SWING_MODE,
                     ATTR_OPERATION_MODE]:
            value = settings.get(attr)
            if value is None:
                continue

            daikin_attr = HA_ATTR_TO_DAIKIN.get(attr)
            if daikin_attr is not None:
                if attr == ATTR_OPERATION_MODE:
                    values[daikin_attr] = HA_STATE_TO_DAIKIN[value]
                elif value in self._list[attr]:
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
            await self._api.device.set(values)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._api.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._api.mac

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

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._set(kwargs)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self.get(ATTR_OPERATION_MODE)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._list.get(ATTR_OPERATION_MODE)

    async def async_set_operation_mode(self, operation_mode):
        """Set HVAC mode."""
        await self._set({ATTR_OPERATION_MODE: operation_mode})

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self.get(ATTR_FAN_MODE)

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        await self._set({ATTR_FAN_MODE: fan_mode})

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._list.get(ATTR_FAN_MODE)

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return self.get(ATTR_SWING_MODE)

    async def async_set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        await self._set({ATTR_SWING_MODE: swing_mode})

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._list.get(ATTR_SWING_MODE)

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    @property
    def is_on(self):
        """Return true if on."""
        return self._api.device.represent(
            HA_ATTR_TO_DAIKIN[ATTR_OPERATION_MODE]
        )[1] != HA_STATE_TO_DAIKIN[STATE_OFF]

    async def async_turn_on(self):
        """Turn device on."""
        await self._api.device.set({})

    async def async_turn_off(self):
        """Turn device off."""
        await self._api.device.set({
            HA_ATTR_TO_DAIKIN[ATTR_OPERATION_MODE]:
            HA_STATE_TO_DAIKIN[STATE_OFF]
        })

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._api.device.represent(
            HA_ATTR_TO_DAIKIN[ATTR_AWAY_MODE]
        )[1] != HA_STATE_TO_DAIKIN[STATE_OFF]

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        await self._api.device.set({HA_ATTR_TO_DAIKIN[ATTR_AWAY_MODE]: '1'})

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        await self._api.device.set({HA_ATTR_TO_DAIKIN[ATTR_AWAY_MODE]: '0'})
