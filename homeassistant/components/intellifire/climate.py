"""Intellifire Climate Entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
)
from homeassistant.components.climate.const import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IntellifireDataUpdateCoordinator
from .const import DEFAULT_THERMOSTAT_TEMP, DOMAIN, LOGGER
from .entity import IntellifireEntity

INTELLIFIRE_CLIMATES: tuple[ClimateEntityDescription, ...] = (
    ClimateEntityDescription(key="climate", name="Thermostat"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure the fan entry.."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data.has_thermostat:
        async_add_entities(
            IntellifireClimate(
                coordinator=coordinator,
                description=description,
            )
            for description in INTELLIFIRE_CLIMATES
        )


class IntellifireClimate(IntellifireEntity, ClimateEntity):
    """Intellifire climate entity."""

    entity_description: ClimateEntityDescription

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp = 0
    _attr_max_temp = 37
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = TEMP_CELSIUS
    last_temp = DEFAULT_THERMOSTAT_TEMP

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        description: ClimateEntityDescription,
    ) -> None:
        """Configure climate entry - and override last_temp if the thermostat is currently on."""
        super().__init__(coordinator, description)

        if coordinator.data.thermostat_on:
            self.last_temp = coordinator.data.thermostat_setpoint_c

    @property
    def hvac_mode(self) -> str:
        """Return current hvac mode."""
        if self.coordinator.read_api.data.thermostat_on:
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Turn on thermostat by setting a target temperature."""
        raw_target_temp = kwargs[ATTR_TEMPERATURE]
        self.last_temp = int(raw_target_temp)
        LOGGER.debug(
            "Setting target temp to %sc %sf",
            int(raw_target_temp),
            (raw_target_temp * 9 / 5) + 32,
        )
        await self.coordinator.control_api.set_thermostat_c(
            temp_c=self.last_temp,
        )

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self.coordinator.read_api.data.temperature_c)

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        return float(self.coordinator.read_api.data.thermostat_setpoint_c)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode to normal or thermostat control."""
        LOGGER.debug(
            "Setting mode to [%s] - using last temp: %s", hvac_mode, self.last_temp
        )

        if hvac_mode == HVACMode.OFF:
            await self.coordinator.control_api.turn_off_thermostat()
            return

        # hvac_mode == HVACMode.HEAT
        # 1) Set the desired target temp
        await self.coordinator.control_api.set_thermostat_c(
            temp_c=self.last_temp,
        )

        # 2) Make sure the fireplace is on!
        if not self.coordinator.read_api.data.is_on:
            await self.coordinator.control_api.flame_on()
