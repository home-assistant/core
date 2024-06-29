"""Anova integration climate."""

from __future__ import annotations

from typing import Any

from anova_wifi import AnovaPrecisionCookerBinarySensor, AnovaPrecisionCookerSensor

from homeassistant import config_entries
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN
from .coordinator import AnovaCoordinator
from .entity import AnovaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        climate = [AnovaSousVideClimateDevice(coordinator)]
        async_add_entities(climate)


class AnovaSousVideClimateDevice(AnovaEntity, ClimateEntity):
    """Anova Sous Vide Climate Device."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: AnovaCoordinator) -> None:
        """Initialize the Anova Sous Vide Climate Device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_unique_id}_climate".lower()

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data["sensors"][
            AnovaPrecisionCookerSensor.WATER_TEMPERATURE
        ]

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data["sensors"][
            AnovaPrecisionCookerSensor.TARGET_TEMPERATURE
        ]

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [HVACMode.OFF, HVACMode.HEAT]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current hvac mode."""
        return (
            HVACMode.HEAT
            if self.coordinator.data["binary_sensors"][
                AnovaPrecisionCookerBinarySensor.COOKING
            ]
            or self.coordinator.data["binary_sensors"][
                AnovaPrecisionCookerBinarySensor.PREHEATING
            ]
            or self.coordinator.data["binary_sensors"][
                AnovaPrecisionCookerBinarySensor.MAINTAINING
            ]
            else HVACMode.OFF
        )

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if (
            self.coordinator.data["binary_sensors"][
                AnovaPrecisionCookerBinarySensor.PREHEATING
            ]
            or self.coordinator.data["binary_sensors"][
                AnovaPrecisionCookerBinarySensor.COOKING
            ]
        ):
            return HVACAction.HEATING

        if self.coordinator.data["binary_sensors"][
            AnovaPrecisionCookerBinarySensor.MAINTAINING
        ]:
            return HVACAction.IDLE

        return HVACAction.OFF

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def min_temp(self) -> float:
        """Return min temp."""
        return TemperatureConverter.convert(
            0, UnitOfTemperature.CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self) -> float:
        """Return max temp."""
        return TemperatureConverter.convert(
            100, UnitOfTemperature.CELSIUS, self.temperature_unit
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.device.set_mode("IDLE")
        elif hvac_mode == HVACMode.HEAT:
            await self.device.set_mode("COOK")
        else:
            raise NotImplementedError

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.device.set_target_temperature(kwargs[ATTR_TEMPERATURE])
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the device."""
        await self.device.set_mode("COOK")

    async def async_turn_off(self) -> None:
        """Turn off the device."""
        await self.device.set_mode("IDLE")
