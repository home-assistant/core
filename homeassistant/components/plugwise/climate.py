"""Plugwise Climate component for Home Assistant."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN, SCHEDULE_OFF, SCHEDULE_ON
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

HVAC_MODES_HEAT_ONLY = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
HVAC_MODES_HEAT_COOL = [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_AUTO, HVAC_MODE_OFF]
THERMOSTAT_CLASSES = ["thermostat", "zone_thermostat", "thermostatic_radiator_valve"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile Thermostats from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        PlugwiseClimateEntity(coordinator, device_id)
        for device_id, device in coordinator.data.devices.items()
        if device["class"] in THERMOSTAT_CLASSES
    )


class PlugwiseClimateEntity(PlugwiseEntity, ClimateEntity):
    """Representation of an Plugwise thermostat."""

    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_preset_modes = None
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_modes = HVAC_MODES_HEAT_ONLY

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{device_id}-climate"
        self._attr_name = self.device.get("name")

        # Determine preset modes
        if presets := self.device.get("presets"):
            self._attr_preset_modes = list(presets)

        # Determine hvac modes and current hvac mode
        if self.coordinator.data.gateway.get("cooling_present"):
            self._attr_hvac_modes = HVAC_MODES_HEAT_COOL

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device["sensors"].get("temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device["sensors"].get("setpoint")

    @property
    def hvac_mode(self) -> str:
        """Return HVAC operation ie. heat, cool mode."""
        if (mode := self.device.get("mode")) is None or mode not in self.hvac_modes:
            return HVAC_MODE_OFF
        return mode

    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation if supported."""
        heater_central_data = self.coordinator.data.devices[
            self.coordinator.data.gateway["heater_id"]
        ]

        if heater_central_data.get("heating_state"):
            return CURRENT_HVAC_HEAT
        if heater_central_data.get("cooling_state"):
            return CURRENT_HVAC_COOL

        return CURRENT_HVAC_IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.device.get("active_preset")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return {
            "available_schemas": self.device.get("available_schedules"),
            "selected_schema": self.device.get("selected_schedule"),
        }

    @plugwise_command
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ((temperature := kwargs.get(ATTR_TEMPERATURE)) is None) or (
            self._attr_max_temp < temperature < self._attr_min_temp
        ):
            raise ValueError("Invalid temperature requested")
        await self.coordinator.api.set_temperature(self.device["location"], temperature)

    @plugwise_command
    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the hvac mode."""
        state = SCHEDULE_OFF
        if hvac_mode == HVAC_MODE_AUTO:
            state = SCHEDULE_ON
            await self.coordinator.api.set_temperature(
                self.device["location"], self.device.get("schedule_temperature")
            )
            self._attr_target_temperature = self.device.get("schedule_temperature")

        await self.coordinator.api.set_schedule_state(
            self.device["location"], self.device.get("last_used"), state
        )

    @plugwise_command
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self.coordinator.api.set_preset(self.device["location"], preset_mode)
