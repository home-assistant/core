"""Support for Switchbot Climate devices."""

from __future__ import annotations

import logging
from typing import Any

import switchbot
from switchbot import (
    ClimateAction as SwitchBotClimateAction,
    ClimateMode as SwitchBotClimateMode,
)

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry
from .entity import SwitchbotEntity, exception_handler

SWITCHBOT_CLIMATE_TO_HASS_HVAC_MODE = {
    SwitchBotClimateMode.HEAT: HVACMode.HEAT,
    SwitchBotClimateMode.OFF: HVACMode.OFF,
}

HASS_HVAC_MODE_TO_SWITCHBOT_CLIMATE = {
    HVACMode.HEAT: SwitchBotClimateMode.HEAT,
    HVACMode.OFF: SwitchBotClimateMode.OFF,
}

SWITCHBOT_ACTION_TO_HASS_HVAC_ACTION = {
    SwitchBotClimateAction.HEATING: HVACAction.HEATING,
    SwitchBotClimateAction.IDLE: HVACAction.IDLE,
    SwitchBotClimateAction.OFF: HVACAction.OFF,
}

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot climate based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([SwitchBotClimateEntity(coordinator)])


class SwitchBotClimateEntity(SwitchbotEntity, ClimateEntity):
    """Representation of a Switchbot Climate device."""

    _device: switchbot.SwitchbotDevice
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "climate"
    _attr_name = None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.max_temperature

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available preset modes."""
        return self._device.preset_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._device.preset_mode

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return SWITCHBOT_CLIMATE_TO_HASS_HVAC_MODE.get(
            self._device.hvac_mode, HVACMode.OFF
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [
            SWITCHBOT_CLIMATE_TO_HASS_HVAC_MODE[mode]
            for mode in self._device.hvac_modes
        ]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return SWITCHBOT_ACTION_TO_HASS_HVAC_ACTION.get(
            self._device.hvac_action, HVACAction.OFF
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @exception_handler
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        return await self._device.set_hvac_mode(
            HASS_HVAC_MODE_TO_SWITCHBOT_CLIMATE[hvac_mode]
        )

    @exception_handler
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        return await self._device.set_preset_mode(preset_mode)

    @exception_handler
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        return await self._device.set_target_temperature(temperature)
