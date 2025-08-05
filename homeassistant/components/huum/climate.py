"""Support for Huum wifi-enabled sauna."""

from __future__ import annotations

import logging
from typing import Any

from huum.const import SaunaStatus
from huum.exceptions import SafetyException

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Huum sauna with config flow."""
    async_add_entities([HuumDevice(entry.runtime_data)])


class HuumDevice(HuumBaseEntity, ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the heater."""
        super().__init__(coordinator)

        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    def min_temp(self) -> int:
        """Return configured minimal temperature."""
        return self.coordinator.data.sauna_config.min_temp

    @property
    def max_temp(self) -> int:
        """Return configured maximum temperature."""
        return self.coordinator.data.sauna_config.max_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self.coordinator.data.status == SaunaStatus.ONLINE_HEATING:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def icon(self) -> str:
        """Return nice icon for heater."""
        if self.hvac_mode == HVACMode.HEAT:
            return "mdi:radiator"
        return "mdi:radiator-off"

    @property
    def current_temperature(self) -> int | None:
        """Return the current temperature."""
        return self.coordinator.data.temperature

    @property
    def target_temperature(self) -> int:
        """Return the temperature we try to reach."""
        return self.coordinator.data.target_temperature or int(self.min_temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            # Make sure to send integers
            # The temperature is not always an integer if the user uses Fahrenheit
            temperature = int(self.target_temperature)
            await self._turn_on(temperature)
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.huum.turn_off()
        await self.coordinator.async_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None or self.hvac_mode != HVACMode.HEAT:
            return
        temperature = int(temperature)

        await self._turn_on(temperature)
        await self.coordinator.async_refresh()

    async def _turn_on(self, temperature: int) -> None:
        try:
            await self.coordinator.huum.turn_on(temperature)
        except (ValueError, SafetyException) as err:
            _LOGGER.error(str(err))
            raise HomeAssistantError(f"Unable to turn on sauna: {err}") from err
