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
from homeassistant.const import UnitOfTemperature
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
HA_TO_CIELO_HVAC: dict[HVACMode, str] = {v: k for k, v in CIELO_TO_HA_HVAC.items()}


def _to_ha_hvac_mode(value: str | HVACMode | None) -> HVACMode | None:
    """Map Cielo string -> HA HVACMode. If already HVACMode, return as-is."""
    if value is None:
        return None
    if isinstance(value, HVACMode):
        return value
    return CIELO_TO_HA_HVAC.get(value)


def _to_cielo_hvac_mode(value: str | HVACMode) -> str:
    """Map HA HVACMode -> Cielo string. If already string, return as-is."""
    if isinstance(value, HVACMode):
        # fallback to 'off' if unexpected, but ideally always found
        return HA_TO_CIELO_HVAC.get(value, "off")
    return value


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
            LOGGER.error("API call response contained no 'data' payload")
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
    def _device_client(self) -> Any:
        """Return the device client, guaranteed not None (typing/runtime safety)."""
        client = self.client
        if client is None:
            raise HomeAssistantError("Device client not available")
        return client

    @property
    def temperature_unit(self) -> str:
        """Return the unit of temperature."""
        return self._device_client.temperature_unit()

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return dynamic feature flags based on the current mode."""
        flags = ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON

        if self.hvac_mode == HVACMode.HEAT_COOL:
            flags |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        elif self._device_client.mode_supports_temperature():
            flags |= ClimateEntityFeature.TARGET_TEMPERATURE

        caps = self._device_client.mode_caps()

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

    def _get_home_assistant_unit(self) -> UnitOfTemperature:
        """Return the Home Assistant temperature unit."""
        return self.hass.config.units.temperature_unit

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature for HEAT_COOL mode."""
        ha_unit = self._get_home_assistant_unit()
        return self._device_client.target_temperature_low(ha_unit)

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature for HEAT_COOL mode."""
        ha_unit = self._get_home_assistant_unit()
        return self._device_client.target_temperature_high(ha_unit)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return _to_ha_hvac_mode(self._device_client.hvac_mode())

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        modes = self._device_client.hvac_modes()
        mapped_modes: list[HVACMode] = []
        for m in modes:
            ha = _to_ha_hvac_mode(m)
            if ha is not None:
                mapped_modes.append(ha)
        return mapped_modes

    @property
    def current_temperature(self) -> float | None:
        """Return the current indoor temperature."""
        return self._device_client.current_temperature()

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._device_client.target_temperature()

    @property
    def min_temp(self) -> float:
        """Return the minimum possible target temperature."""
        return self._device_client.min_temp()

    @property
    def max_temp(self) -> float:
        """Return the maximum possible target temperature."""
        return self._device_client.max_temp()

    @property
    def target_temperature_step(self) -> float | None:
        """Return the precision of the thermostat."""
        ha_unit = self._get_home_assistant_unit()
        return self._device_client.target_temperature_step(ha_unit)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self._device_client.fan_mode()

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self._device_client.fan_modes()

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        return self._device_client.swing_modes()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._device_client.preset_mode()

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available preset modes."""
        return self._device_client.preset_modes()

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self.device_data.swing_mode if self.device_data else None

    @property
    def precision(self) -> float:
        """Return the precision of the thermostat."""
        ha_unit = self._get_home_assistant_unit()
        return self._device_client.precision(ha_unit)

    @async_handle_api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        ha_unit = self._get_home_assistant_unit()
        return await self._device_client.async_set_temperature(ha_unit, **kwargs)

    @async_handle_api_call
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        return await self._device_client.async_set_fan_mode(fan_mode)

    @async_handle_api_call
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        return await self._device_client.async_set_preset_mode(preset_mode)

    @async_handle_api_call
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        return await self._device_client.async_set_hvac_mode(
            _to_cielo_hvac_mode(hvac_mode)
        )

    @async_handle_api_call
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        return await self._device_client.async_set_swing_mode(swing_mode)

    async def async_turn_on(self) -> None:
        """Turn the climate device on."""
        modes = self.hvac_modes or []

        # Select the first supported non-off mode when turning on
        for mode in modes:
            if mode != HVACMode.OFF:
                await self.async_set_hvac_mode(mode)
                return

        if not modes:
            raise HomeAssistantError("No HVAC modes available to turn on device")

        raise HomeAssistantError("No non-off HVAC modes available to turn on device")

    async def async_turn_off(self) -> None:
        """Turn the climate device off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
