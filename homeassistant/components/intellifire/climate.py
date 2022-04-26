"""Intellifire Climate Entities."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.climate import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN, LOGGER
from .entity import IntellifireEntity


@dataclass
class IntellifireClimateEntityDescription(ClimateEntityDescription):
    """Describes a fan entity."""


INTELLIFIRE_CLIMATES: tuple[IntellifireClimateEntityDescription, ...] = (
    IntellifireClimateEntityDescription(key="climate", name="climate"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fans."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IntellifireClimate(
            coordinator=coordinator,
            description=description,
        )
        for description in INTELLIFIRE_CLIMATES
    )


class IntellifireClimate(IntellifireEntity, ClimateEntity):
    """Intellifire climate entity."""

    entity_description: IntellifireClimateEntityDescription

    _attr_hvac_modes = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
    _attr_min_temp = 0
    _attr_max_temp = 37
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = TEMP_CELSIUS
    last_temp = 21

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable entity if configured with a thermostat."""
        enabled = bool(self.coordinator.data.has_thermostat)
        # Can i use a walrus operator here?
        if not enabled:
            LOGGER.info(
                "Disabling climate sensor - IntelliFire device does not appear to have one"
            )
            return False
        return True

    @property
    def hvac_mode(self) -> str:
        """Return current hvac mode."""
        if self.coordinator.read_api.data.thermostat_on:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    async def async_set_temperature(self, **kwargs) -> None:
        """Turn on thermostat by setting a target temperature."""
        raw_target_temp = kwargs[ATTR_TEMPERATURE]
        self.last_temp = int(raw_target_temp)
        LOGGER.info(
            "Setting target temp to %sc %sf",
            int(raw_target_temp),
            (raw_target_temp * 9 / 5) + 32,
        )
        await self.coordinator.control_api.set_thermostat_c(
            fireplace=self.coordinator.control_api.default_fireplace,
            temp_c=self.last_temp,
        )

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self.coordinator.read_api.data.temperature_c)

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return float(self.coordinator.read_api.data.thermostat_setpoint_c)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode to normal or thermostat control."""
        LOGGER.info(
            "Setting mode to [%s] - using last temp: %s", hvac_mode, self.last_temp
        )

        # Dear Reviewer - Is there a way to use a := here?
        if hvac_mode == HVAC_MODE_HEAT:
            # 1) Set the desired target temp
            await self.coordinator.control_api.set_thermostat_c(
                fireplace=self.coordinator.control_api.default_fireplace,
                temp_c=self.last_temp,
            )

            # 2) Make sure the fireplace is on!
            if not self.coordinator.read_api.data.is_on:
                await self.coordinator.control_api.flame_on(
                    fireplace=self.coordinator.control_api.default_fireplace,
                )

        if hvac_mode == HVAC_MODE_OFF:
            await self.coordinator.control_api.turn_off_thermostat(
                fireplace=self.coordinator.control_api.default_fireplace
            )
