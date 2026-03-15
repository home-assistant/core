"""Comet Blue climate integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity

LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
MIN_TEMP = 7.5
MAX_TEMP = 28.5

DEFAULT_PRESETS = {PRESET_COMFORT, PRESET_ECO}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the client entities."""

    coordinator: CometBlueDataUpdateCoordinator = entry.runtime_data
    async_add_entities([CometBlueClimateEntity(coordinator)])


class CometBlueClimateEntity(CometBlueBluetoothEntity, ClimateEntity):
    """A Comet Blue Climate climate entity."""

    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_name = None
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_ECO,
        PRESET_AWAY,
        PRESET_COMFORT,
    ]
    _attr_supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: CometBlueDataUpdateCoordinator) -> None:
        """Initialize CometBlueClimateEntity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}-climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data["currentTemp"]

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        return self.coordinator.data["manualTemp"]

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature."""
        return self.coordinator.data["targetTempHigh"]

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature."""
        return self.coordinator.data["targetTempLow"]

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation mode."""
        if self.target_temperature == MIN_TEMP:
            return HVACMode.OFF
        if self.target_temperature == MAX_TEMP:
            return HVACMode.HEAT
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac action if supported."""

        if self.target_temperature == MIN_TEMP:
            return HVACAction.OFF
        if (self.target_temperature or 0.0) > (
            self.target_temperature_low or 0.0
        ) or self.target_temperature == MAX_TEMP:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        # presets have an order in which they are displayed on TRV:
        # away, comfort, eco, none (manual)
        if (
            self.coordinator.data["holiday"].get("start") is None
            and self.coordinator.data["holiday"].get("end") is not None
            and self.target_temperature
            == self.coordinator.data["holiday"].get("temperature")
        ):
            return PRESET_AWAY
        if self.target_temperature == self.target_temperature_high:
            return PRESET_COMFORT
        if self.target_temperature == self.target_temperature_low:
            return PRESET_ECO
        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Will only show presets that are supported by the device.
        """
        if self.preset_mode:
            return list(DEFAULT_PRESETS | {self.preset_mode})
        return list(DEFAULT_PRESETS)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""

        if self.preset_mode == PRESET_AWAY:
            raise ValueError(
                "Cannot adjust TRV remotely, manually disable 'holiday' mode on TRV first"
            )

        await self.coordinator.send_command(
            "set_temperature_async",
            {
                "values": {
                    # manual temperature always needs to be set, otherwise TRV will turn OFF
                    "manualTemp": kwargs.get(ATTR_TEMPERATURE)
                    or self.target_temperature,
                    "targetTempLow": kwargs.get(ATTR_TARGET_TEMP_LOW),
                    "targetTempHigh": kwargs.get(ATTR_TARGET_TEMP_HIGH),
                }
            },
            self.entity_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""

        if self.preset_modes and preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")
        if preset_mode in [PRESET_NONE, PRESET_AWAY]:
            raise ValueError(f"Unable to set preset '{preset_mode}', display only.")
        if preset_mode == PRESET_ECO:
            return await self.async_set_temperature(
                temperature=self.target_temperature_low
            )
        if preset_mode == PRESET_COMFORT:
            return await self.async_set_temperature(
                temperature=self.target_temperature_high
            )
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if hvac_mode == HVACMode.OFF:
            return await self.async_set_temperature(temperature=MIN_TEMP)
        if hvac_mode == HVACMode.HEAT:
            return await self.async_set_temperature(temperature=MAX_TEMP)
        if hvac_mode == HVACMode.AUTO:
            return await self.async_set_temperature(
                temperature=self.target_temperature_low
            )
        raise ValueError(f"Unknown HVAC mode '{hvac_mode}'")

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
