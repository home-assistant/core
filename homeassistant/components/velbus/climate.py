"""Support for Velbus thermostat."""
import logging

from velbus.util import VelbusException

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus binary sensor based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    modules_data = hass.data[DOMAIN][entry.entry_id]["climate"]
    entities = []
    for address, channel in modules_data:
        module = cntrl.get_module(address)
        entities.append(VelbusClimate(module, channel))
    async_add_entities(entities)


class VelbusClimate(VelbusEntity, ClimateDevice):
    """Representation of a Velbus thermostat."""

    @property
    def supported_features(self):
        """Return the list off supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the unit this state is expressed in."""
        if self._module.get_unit(self._channel) == TEMP_CELSIUS:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._module.get_state(self._channel)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._module.get_climate_target()

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        try:
            self._module.set_temp(temp)
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)
            return
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
