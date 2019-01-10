"""
Support for Velbus thermostat.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.velbus/
"""
import logging

from homeassistant.components.climate import (
    STATE_HEAT, SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.components.velbus import (
    DOMAIN as VELBUS_DOMAIN, VelbusEntity)
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Velbus thermostat platform."""
    if discovery_info is None:
        return

    sensors = []
    for sensor in discovery_info:
        module = hass.data[VELBUS_DOMAIN].get_module(sensor[0])
        channel = sensor[1]
        sensors.append(VelbusClimate(module, channel))

    async_add_entities(sensors)


class VelbusClimate(VelbusEntity, ClimateDevice):
    """Representation of a Velbus thermostat."""

    @property
    def supported_features(self):
        """Return the list off supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit this state is expressed in."""
        if self._module.get_unit(self._channel) == '°C':
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._module.get_state(self._channel)

    @property
    def current_operation(self):
        """Return current operation."""
        return STATE_HEAT

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._module.get_climate_target()

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._module.set_temp(temp)
        self.schedule_update_ha_state()
