"""Climate platform for Teslemetry integration."""

from __future__ import annotations

from typing import Any

from tesla_fleet_api.const import Scope

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TeslemetryClimateSide
from .context import handle_command
from .entity import TeslemetryVehicleEntity
from .models import TeslemetryVehicleData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Teslemetry Climate platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TeslemetryClimateEntity(vehicle, TeslemetryClimateSide.DRIVER, data.scopes)
        for vehicle in data.vehicles
    )


class TeslemetryClimateEntity(TeslemetryVehicleEntity, ClimateEntity):
    """Vehicle Location Climate Class."""

    _attr_precision = PRECISION_HALVES
    _attr_min_temp = 15
    _attr_max_temp = 28
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = ["off", "keep", "dog", "camp"]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        data: TeslemetryVehicleData,
        side: TeslemetryClimateSide,
        scopes: Scope,
    ) -> None:
        """Initialize the climate."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = ClimateEntityFeature(0)

        super().__init__(
            data,
            side,
        )

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        if self.get("climate_state_is_climate_on"):
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.get("climate_state_inside_temp")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.get(f"climate_state_{self.key}_setting")

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.get("climate_state_max_avail_temp", self._attr_max_temp)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.get("climate_state_min_avail_temp", self._attr_min_temp)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.get("climate_state_climate_keeper_mode")

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        self.raise_for_scope()
        with handle_command():
            await self.wake_up_if_asleep()
            await self.api.auto_conditioning_start()
        self.set(("climate_state_is_climate_on", True))

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        self.raise_for_scope()
        with handle_command():
            await self.wake_up_if_asleep()
            await self.api.auto_conditioning_stop()
        self.set(
            ("climate_state_is_climate_on", False),
            ("climate_state_climate_keeper_mode", "off"),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""
        temp = kwargs[ATTR_TEMPERATURE]
        with handle_command():
            await self.wake_up_if_asleep()
            await self.api.set_temps(
                driver_temp=temp,
                passenger_temp=temp,
            )

        self.set((f"climate_state_{self.key}_setting", temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the climate mode and state."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the climate preset mode."""
        with handle_command():
            await self.wake_up_if_asleep()
            await self.api.set_climate_keeper_mode(
                climate_keeper_mode=self._attr_preset_modes.index(preset_mode)
            )
        self.set(
            (
                "climate_state_climate_keeper_mode",
                preset_mode,
            ),
            (
                "climate_state_is_climate_on",
                preset_mode != self._attr_preset_modes[0],
            ),
        )
