"""Support for Cielo home thermostats and Smart AC Controllers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from cieloconnectapi import AuthenticationError

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CIELO_ERRORS, LOGGER, TIMEOUT
from .coordinator import CieloDataUpdateCoordinator, CieloHomeConfigEntry
from .entity import CieloDeviceBaseEntity

_T = TypeVar("_T", bound="CieloDeviceBaseEntity")
_P = ParamSpec("_P")

PARALLEL_UPDATES = 0

CIELO_TO_HA_HVAC: dict[str, HVACMode] = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "fan": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "auto": HVACMode.AUTO,
    "heat_cool": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CieloHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Cielo climate platform."""
    coordinator = entry.runtime_data
    devices = coordinator.data.parsed
    async_add_entities([CieloClimate(coordinator, dev_id) for dev_id in devices])


def async_handle_api_call(
    function: Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]]:
    """Decorate api calls to handle exceptions and update state."""

    async def wrap_api_call(*args: Any, **kwargs: Any) -> None:
        """Wrap services for api calls."""
        entity: _T = args[0]
        res: Any = None

        try:
            async with asyncio.timeout(TIMEOUT):
                res = await function(*args, **kwargs)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err

        except CIELO_ERRORS as err:
            if isinstance(err, TimeoutError):
                raise HomeAssistantError("API call timed out") from err
            raise HomeAssistantError from err

        LOGGER.debug(
            "API call result for entity %s: type=%s keys=%s",
            entity.entity_id,
            type(res),
            list(res.keys()) if isinstance(res, dict) else None,
        )

        if not isinstance(res, dict):
            LOGGER.error(
                "API function did not return a dictionary for entity %s, got %s",
                entity.entity_id,
                type(res),
            )
            raise HomeAssistantError("Invalid API response format")

        data: dict[str, Any] | None = res.get("data")

        if not data:
            raise HomeAssistantError("API response contained no data payload")

        await entity.coordinator.async_apply_action_result(entity.device_id, data)

    return wrap_api_call


class CieloClimate(CieloDeviceBaseEntity, ClimateEntity):
    """Representation of a Cielo Smart AC Controller."""

    _attr_name = None
    _attr_translation_key = "climate_device"

    def __init__(self, coordinator: CieloDataUpdateCoordinator, device_id: str) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id

    @property
    def temperature_unit(self) -> str:
        """Return the unit of temperature."""
        return self.client.temperature_unit()

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return dynamic feature flags based on the current mode."""
        flags = ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON

        if self.hvac_mode == HVACMode.HEAT_COOL:
            flags |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        elif self.client.mode_supports_temperature():
            flags |= ClimateEntityFeature.TARGET_TEMPERATURE

        caps = self.client.mode_caps()

        if caps.get("fan_levels"):
            flags |= ClimateEntityFeature.FAN_MODE

        if caps.get("swing"):
            flags |= ClimateEntityFeature.SWING_MODE

        if self.device_data and self.device_data.preset_modes:
            flags |= ClimateEntityFeature.PRESET_MODE

        return flags

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity, if available."""
        if self.device_data:
            return self.device_data.humidity
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature for HEAT_COOL mode."""
        return self.client.target_temperature_low(self.temperature_unit)

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature for HEAT_COOL mode."""
        return self.client.target_temperature_high(self.temperature_unit)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode.

        The backend already maps device HVAC states to Home Assistant HVACMode
        values, ensuring consistency with HA climate expectations and UI icons.
        """
        return self.client.hvac_mode()

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes.

        Device HVAC modes are provided by the backend and translated to
        Home Assistant HVACMode values using the CIELO_TO_HA_HVAC mapping.
        This ensures the entity exposes only HA-compatible HVAC modes.
        """
        modes = self.client.hvac_modes()
        return [CIELO_TO_HA_HVAC[m] for m in modes if m in CIELO_TO_HA_HVAC]

    @property
    def current_temperature(self) -> float | None:
        """Return the current indoor temperature."""
        return self.client.current_temperature()

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.client.target_temperature()

    @property
    def min_temp(self) -> float:
        """Return the minimum possible target temperature."""
        return self.client.min_temp()

    @property
    def max_temp(self) -> float:
        """Return the maximum possible target temperature."""
        return self.client.max_temp()

    @property
    def target_temperature_step(self) -> float | None:
        """Return the precision of the thermostat."""
        return self.client.target_temperature_step(self.temperature_unit)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self.client.fan_mode()

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes.

        Fan modes are normalized in the backend to snake_case values that
        match Home Assistant expectations (e.g. "low", "medium", "high", "auto").
        This allows HA to translate and display icons correctly using the
        integration strings definitions.
        """
        return self.client.fan_modes()

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes.

        Swing modes are normalized in the backend to snake_case values
        compatible with Home Assistant (e.g. "auto", "swing", "pos1", "pos2").
        These values align with the integration translations so HA can display
        proper labels and icons.
        """
        return self.client.swing_modes()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.client.preset_mode()

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available preset modes.

        Preset modes are normalized in the backend to snake_case values that
        match Home Assistant expectations (e.g. "home", "away", "sleep", "pets").
        This allows HA to translate and display icons correctly using the
        integration strings definitions.
        """
        return self.client.preset_modes()

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self.device_data.swing_mode if self.device_data else None

    @property
    def precision(self) -> float:
        """Return the precision of the thermostat."""
        return self.client.precision(self.temperature_unit)

    @async_handle_api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        return await self.client.async_set_temperature(self.temperature_unit, **kwargs)

    @async_handle_api_call
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        return await self.client.async_set_fan_mode(fan_mode)

    @async_handle_api_call
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        return await self.client.async_set_preset_mode(preset_mode)

    @async_handle_api_call
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        return await self.client.async_set_hvac_mode(hvac_mode)

    @async_handle_api_call
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        return await self.client.async_set_swing_mode(swing_mode)

    async def async_turn_on(self) -> None:
        """Turn the climate device on."""
        modes = self.hvac_modes or []

        # Select the first supported non-off mode when turning on
        for mode in modes:
            if mode != HVACMode.OFF:
                await self.async_set_hvac_mode(mode)
                return

        raise HomeAssistantError("No non-off HVAC modes available to turn on device")

    async def async_turn_off(self) -> None:
        """Turn the climate device off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
