"""Support for Cielo home thermostats and Smart AC Controllers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CIELO_ERRORS, LOGGER, TIMEOUT
from .coordinator import CieloDataUpdateCoordinator, CieloHomeConfigEntry
from .entity import CieloDeviceBaseEntity

_T = TypeVar("_T", bound="CieloDeviceBaseEntity")
_P = ParamSpec("_P")


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

    async def wrap_api_call(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
        """Wrap services for api calls."""
        entity: _T = args[0]
        res: Any = None

        if entity.client and entity.device_data:
            entity.client.device_data = entity.device_data

        try:
            async with asyncio.timeout(TIMEOUT):
                res = await function(*args, **kwargs)

        except CIELO_ERRORS as err:
            LOGGER.error("API call failed for entity %s: %s", entity.entity_id, err)
            raise HomeAssistantError from err
        except TimeoutError as err:
            LOGGER.error("API call timed out for entity %s: %s", entity.entity_id, err)
            raise HomeAssistantError("API call timed out") from err

        LOGGER.debug("API call result for entity %s: %s", entity.entity_id, res)

        if not isinstance(res, dict):
            LOGGER.error("API function did not return a dictionary: %s", res)
            return None

        data: dict[str, Any] | None = res.get("data")

        if not data:
            LOGGER.error("API call response contained no 'data' payload")
            return None

        if entity.device_data is None:
            return None

        try:
            entity.device_data.apply_update(data)
        except (KeyError, ValueError, TypeError) as err:
            LOGGER.error(
                "Failed to apply API response data for entity %s: %s",
                entity.entity_id,
                err,
            )
            return None

        entity.async_write_ha_state()
        return data

    return wrap_api_call


class CieloClimate(CieloDeviceBaseEntity, ClimateEntity):
    """Representation of a Cielo Smart AC Controller."""

    _attr_name = None
    _attr_translation_key = "climate_device"

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

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
        flags = ClimateEntityFeature(0)

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

        flags |= ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON

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
        return self.client.target_temperature_low(ha_unit)

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature for HEAT_COOL mode."""
        ha_unit = self._get_home_assistant_unit()
        return self.client.target_temperature_high(ha_unit)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return self.client.hvac_mode()

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return self.client.hvac_modes()

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
        ha_unit = self._get_home_assistant_unit()
        return self.client.target_temperature_step(ha_unit)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self.client.fan_mode()

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self.client.fan_modes()

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        return self.client.swing_modes()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.client.preset_mode()

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available preset modes."""
        return self.client.preset_modes()

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self.device_data.swing_mode if self.device_data else None

    @property
    def available(self) -> bool:
        """Return if the device is available and online."""
        if not super().available:
            return False
        if self.device_data is None:
            return False
        return bool(self.device_data.device_status)

    @property
    def precision(self) -> float:
        """Return the precision of the thermostat."""
        ha_unit = self._get_home_assistant_unit()
        return self.client.precision(ha_unit)

    @async_handle_api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        ha_unit = self._get_home_assistant_unit()
        return await self.client.async_set_temperature(ha_unit, **kwargs)

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
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    async def async_turn_off(self) -> None:
        """Turn the climate device off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
