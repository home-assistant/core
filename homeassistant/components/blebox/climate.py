"""BleBox climate entity."""
from datetime import timedelta
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox climate entity."""

    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxClimateEntity, "climates"
    )


class BleBoxClimateEntity(BleBoxEntity, ClimateEntity):
    """Representation of a BleBox climate feature (saunaBox)."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_temperature_unit = TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return the desired HVAC mode."""
        if self._feature.is_on is None:
            return None

        return HVACMode.HEAT if self._feature.is_on else HVACMode.OFF

    @property
    def hvac_action(self):
        """Return the actual current HVAC action."""
        if not (is_on := self._feature.is_on):
            return None if is_on is None else HVACAction.OFF

        # NOTE: In practice, there's no need to handle case when is_heating is None
        return HVACAction.HEATING if self._feature.is_heating else HVACAction.IDLE

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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the climate entity mode."""
        if hvac_mode == HVACMode.HEAT:
            await self._feature.async_on()
            return

        await self._feature.async_off()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the thermostat temperature."""
        value = kwargs[ATTR_TEMPERATURE]
        await self._feature.async_set_temperature(value)
