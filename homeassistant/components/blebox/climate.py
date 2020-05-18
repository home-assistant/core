"""BleBox climate entity."""

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_TO_CLIMATE_HVAC_MODE, BLEBOX_TO_CURRENT_HVAC_MODE


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a BleBox climate entity."""

    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxClimateEntity, "climates"
    )


class BleBoxClimateEntity(BleBoxEntity, ClimateDevice):
    """Representation of a BleBox climate feature (saunaBox)."""

    @property
    def supported_features(self):
        """Return the supported climate features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_mode(self):
        """Return the desired HVAC mode."""
        return BLEBOX_TO_CLIMATE_HVAC_MODE[self._feature.is_on]

    @property
    def hvac_action(self):
        """Return the actual current HVAC action."""
        is_on = self._feature.is_on
        if not is_on:
            return None if is_on is None else CURRENT_HVAC_OFF

        heating = self._feature.is_heating
        return BLEBOX_TO_CURRENT_HVAC_MODE[heating]

    @property
    def hvac_modes(self):
        """Return a list of possible HVAC modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_HEAT]

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return TEMP_CELSIUS

    @property
    def max_temp(self):
        """Return the maximum temperature supported."""
        return self._feature.max_temp

    @property
    def min_temp(self):
        """Return the maximum temperature supported."""
        return self._feature.min_temp

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._feature.current

    @property
    def target_temperature(self):
        """Return the desired thermostat temperature."""
        return self._feature.desired

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the climate entity mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            return await self._feature.async_on()

        return await self._feature.async_off()

    async def async_set_temperature(self, **kwargs):
        """Set the thermostat temperature."""
        value = kwargs[ATTR_TEMPERATURE]
        await self._feature.async_set_temperature(value)
