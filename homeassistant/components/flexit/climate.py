"""Platform for Flexit AC units with CI66 Modbus adapter."""
from __future__ import annotations

import logging

from pyflexit.pyflexit import pyflexit
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.modbus.const import CONF_HUB, DEFAULT_HUB, MODBUS_DOMAIN
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    DEVICE_DEFAULT_NAME,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_SLAVE): vol.All(int, vol.Range(min=0, max=32)),
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Flexit Platform."""
    modbus_slave = config.get(CONF_SLAVE)
    name = config.get(CONF_NAME)
    hub = hass.data[MODBUS_DOMAIN][config.get(CONF_HUB)]
    add_entities([Flexit(hub, modbus_slave, name)], True)


class Flexit(ClimateEntity):
    """Representation of a Flexit AC unit."""

    def __init__(self, hub, modbus_slave, name):
        """Initialize the unit."""
        self._hub = hub
        self._name = name
        self._slave = modbus_slave
        self._target_temperature = None
        self._current_temperature = None
        self._current_fan_mode = None
        self._current_operation = None
        self._fan_modes = ["Off", "Low", "Medium", "High"]
        self._current_operation = None
        self._filter_hours = None
        self._filter_alarm = None
        self._heat_recovery = None
        self._heater_enabled = False
        self._heating = None
        self._cooling = None
        self._alarm = False
        self.unit = pyflexit(hub, modbus_slave)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update unit attributes."""
        if not self.unit.update():
            _LOGGER.warning("Modbus read failed")

        self._target_temperature = self.unit.get_target_temp
        self._current_temperature = self.unit.get_temp
        self._current_fan_mode = self._fan_modes[self.unit.get_fan_speed]
        self._filter_hours = self.unit.get_filter_hours
        # Mechanical heat recovery, 0-100%
        self._heat_recovery = self.unit.get_heat_recovery
        # Heater active 0-100%
        self._heating = self.unit.get_heating
        # Cooling active 0-100%
        self._cooling = self.unit.get_cooling
        # Filter alarm 0/1
        self._filter_alarm = self.unit.get_filter_alarm
        # Heater enabled or not. Does not mean it's necessarily heating
        self._heater_enabled = self.unit.get_heater_enabled
        # Current operation mode
        self._current_operation = self.unit.get_operation

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "filter_hours": self._filter_hours,
            "filter_alarm": self._filter_alarm,
            "heat_recovery": self._heat_recovery,
            "heating": self._heating,
            "heater_enabled": self._heater_enabled,
            "cooling": self._cooling,
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_COOL]

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.unit.set_temp(self._target_temperature)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        self.unit.set_fan_speed(self._fan_modes.index(fan_mode))
