"""Support for Velbus thermostat."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("climate"):
        entities.append(VelbusClimate(channel))
    async_add_entities(entities)


class VelbusClimate(VelbusEntity, ClimateEntity):
    """Representation of a Velbus thermostat."""

    @property
    def supported_features(self):
        """Return the list off supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the unit."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._channel.get_state()

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
        return self._channel.get_climate_target()

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._channel.set_temp(temp)
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
