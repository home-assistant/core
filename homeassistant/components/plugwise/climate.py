"""Plugwise Climate component for Home Assistant."""
from __future__ import annotations

from collections.abc import Mapping
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

from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN, THERMOSTAT_CLASSES
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command


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
        if device["dev_class"] in THERMOSTAT_CLASSES
    )


class PlugwiseClimateEntity(PlugwiseEntity, ClimateEntity):
    """Representation of an Plugwise thermostat."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{device_id}-climate"

        # Determine preset modes
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if presets := self.device.get("preset_modes"):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = presets

        # Determine hvac modes and current hvac mode
        self._attr_hvac_modes = [HVACMode.HEAT]
        if self.coordinator.data.gateway.get("cooling_present"):
            self._attr_hvac_modes.append(HVACMode.COOL)
        if self.device.get("available_schedules") != ["None"]:
            self._attr_hvac_modes.append(HVACMode.AUTO)

        self._attr_min_temp = self.device.get("lower_bound", DEFAULT_MIN_TEMP)
        self._attr_max_temp = self.device.get("upper_bound", DEFAULT_MAX_TEMP)
        if resolution := self.device.get("resolution"):
            # Ensure we don't drop below 0.1
            self._attr_target_temperature_step = max(resolution, 0.1)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device["sensors"].get("temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device["sensors"].get("setpoint")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC operation ie. heat, cool mode."""
        if (mode := self.device.get("mode")) is None or mode not in self.hvac_modes:
            return HVACMode.HEAT
        return HVACMode(mode)

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        # When control_state is present, prefer this data
        if "control_state" in self.device:
            if self.device.get("control_state") == "cooling":
                return HVACAction.COOLING
            # Support preheating state as heating, until preheating is added as a separate state
            if self.device.get("control_state") in ["heating", "preheating"]:
                return HVACAction.HEATING
        else:
            heater_central_data = self.coordinator.data.devices[
                self.coordinator.data.gateway["heater_id"]
            ]
            if heater_central_data["binary_sensors"].get("heating_state"):
                return HVACAction.HEATING
            if heater_central_data["binary_sensors"].get("cooling_state"):
                return HVACAction.COOLING

        return HVACAction.IDLE

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
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the hvac mode."""
        await self.coordinator.api.set_schedule_state(
            self.device["location"],
            self.device.get("last_used"),
            "on" if hvac_mode == HVACMode.AUTO else "off",
        )

    @plugwise_command
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self.coordinator.api.set_preset(self.device["location"], preset_mode)
