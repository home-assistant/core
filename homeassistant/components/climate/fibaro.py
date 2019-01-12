"""
Support for Fibaro thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.fibaro/
"""
import logging

from homeassistant.util import convert
from homeassistant.components.climate import (
    ClimateDevice, STATE_AUTO, STATE_COOL,
    STATE_HEAT, ENTITY_ID_FORMAT, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE)
from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
    ATTR_TEMPERATURE)

from homeassistant.components.fibaro import (
    FIBARO_DEVICES, FibaroDevice)

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)

OPERATION_LIST = [STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_OFF]
FAN_OPERATION_LIST = [STATE_ON, STATE_AUTO]

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Fibaro controller devices."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroThermostat(device)
         for device in hass.data[FIBARO_DEVICES]['climate']], True)


class FibaroThermostat(FibaroDevice, ClimateDevice):
    """Representation of a Vera Thermostat."""

    def __init__(self, fibaro_device):
        """Initialize the Vera device."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        mode = self.vera_device.get_fan_mode()
        if mode == "ContinuousOn":
            return FAN_OPERATION_LIST[0]  # on
        if mode == "Auto":
            return FAN_OPERATION_LIST[1]  # auto
        return "Auto"

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""

        if self.fibaro_device.properties.unit == 'F':
            return TEMP_FAHRENHEIT

        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self.fibaro_device.properties.value)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self.fibaro_device.properties.targetLevel)

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self.fibaro_device.action("setTargetLevel", kwargs.get(ATTR_TEMPERATURE))
