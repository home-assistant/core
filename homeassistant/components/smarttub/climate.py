"""Platform for climate integration."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature

from . import SmartTubEntity
from .const import DOMAIN, SMARTTUB_CONTROLLER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entity for the thermostat in the tub."""

    controller = hass.data[DOMAIN][entry.unique_id][SMARTTUB_CONTROLLER]

    async_add_entities(
        [SmartTubThermostat(controller, spa_id) for spa_id in controller.spa_ids]
    )

    return True


class SmartTubThermostat(SmartTubEntity, ClimateEntity):
    """The target water temperature for the spa."""

    def __init__(self, controller, spa_id):
        """Initialize the entity."""
        super().__init__(controller, spa_id, "thermostat")

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        heater_status = self.controller.get_heater_status(self.spa_id)
        if heater_status == "ON":
            return CURRENT_HVAC_HEAT
        if heater_status == "OFF":
            return CURRENT_HVAC_IDLE
        raise ValueError(f"unknown heater status: {heater_status}")

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def hvac_mode(self):
        """Return the current hvac mode.

        SmartTub devices don't seem to have the option of disabling the heater,
        so this is always HVAC_MODE_HEAT.
        """
        return HVAC_MODE_HEAT

    async def async_set_hvac_mode(self, hvac_mode: str):
        """Set new target hvac mode.

        As with hvac_mode, we don't really have an option here.
        """
        if hvac_mode == HVAC_MODE_HEAT:
            return
        raise NotImplementedError(hvac_mode)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        min_temp = self.controller.get_minimum_target_water_temperature(self.spa_id)
        return convert_temperature(min_temp, TEMP_CELSIUS, self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        max_temp = self.controller.get_maximum_target_water_temperature(self.spa_id)
        return convert_temperature(max_temp, TEMP_CELSIUS, self.temperature_unit)

    @property
    def supported_features(self):
        """Return the set of supported features.

        Only target temperature is supported.
        """
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def current_temperature(self):
        """Return the current water temperature."""
        return self.controller.get_current_water_temperature(self.spa_id)

    @property
    def target_temperature(self):
        """Return the target water temperature."""
        return self.controller.get_target_water_temperature(self.spa_id)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.controller.set_target_water_temperature(self.spa_id, temperature)
