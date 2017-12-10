"""
Support for the Daikin HVAC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.daikin/
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import (
    ClimateDevice,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,

    ATTR_OPERATION_MODE, ATTR_FAN_MODE, ATTR_SWING_MODE,
    ATTR_CURRENT_TEMPERATURE, ATTR_TARGET_TEMP_STEP,
    PLATFORM_SCHEMA
)
from homeassistant.const import (
    CONF_HOST, CONF_NAME
)

from homeassistant.components.daikin import (
    manual_device_setup,
    ATTR_TARGET_TEMPERATURE
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_FAN_MODE |
                 SUPPORT_OPERATION_MODE |
                 SUPPORT_SWING_MODE)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Daikin HVAC platform."""
    if discovery_info is not None:
        host = discovery_info['ip']
        name = None
        _LOGGER.info("Discovered a Daikin AC on %s", host)
    else:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
        _LOGGER.info("Added Daikin AC on %s", host)

    device = manual_device_setup(hass, host, name)
    add_devices([DaikinClimate(device)], True)


class DaikinClimate(ClimateDevice):
    """Representation of a Daikin HVAC."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device

    @property
    def unique_id(self):
        """Return the ID of this AC."""
        return "{}.{}".format(self.__class__, self._device.ip)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return self._device.temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get(ATTR_CURRENT_TEMPERATURE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get(ATTR_TARGET_TEMPERATURE)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._device.get(ATTR_TARGET_TEMP_STEP)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        self._device.set(kwargs)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._device.get(ATTR_OPERATION_MODE)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._device.operation_list

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode."""
        self._device.set({ATTR_OPERATION_MODE: operation_mode})

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._device.get(ATTR_FAN_MODE)

    def set_fan_mode(self, fan):
        """Set fan mode."""
        self._device.set({ATTR_FAN_MODE: fan})

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._device.fan_list

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return self._device.get(ATTR_SWING_MODE)

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self._device.set({ATTR_SWING_MODE: swing_mode})

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._device.swing_list

    def update(self):
        """Retrieve latest state."""
        self._device.update()
