"""Sandbox proxy for ``climate`` entities."""

from typing import Any, override

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_HORIZONTAL_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxClimateEntity(SandboxProxyEntity, ClimateEntity):
    """Proxy for a ``climate`` entity in a sandbox."""

    _features_flag = ClimateEntityFeature

    @property
    @override
    def temperature_unit(self) -> str:
        """Return the unit declared by the sandbox-side entity."""
        return str(
            self.description.capabilities.get(
                "temperature_unit", UnitOfTemperature.CELSIUS
            )
        )

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the cached HVAC mode."""
        value = self._state_cache.get("state")
        if value is None or value == "unavailable":
            return None
        try:
            return HVACMode(value)
        except ValueError:
            return None

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return advertised HVAC modes."""
        modes = self.description.capabilities.get(ATTR_HVAC_MODES) or []
        return [HVACMode(m) for m in modes if m in HVACMode._value2member_map_]

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the cached current HVAC action."""
        value = self._state_cache.get(ATTR_HVAC_ACTION)
        if value is None:
            return None
        try:
            return HVACAction(value)
        except ValueError:
            return None

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the cached current temperature."""
        value = self._state_cache.get(ATTR_CURRENT_TEMPERATURE)
        return None if value is None else float(value)

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the cached target temperature."""
        value = self._state_cache.get(ATTR_TEMPERATURE)
        return None if value is None else float(value)

    @property
    @override
    def target_temperature_high(self) -> float | None:
        """Return the cached high target temperature."""
        value = self._state_cache.get(ATTR_TARGET_TEMP_HIGH)
        return None if value is None else float(value)

    @property
    @override
    def target_temperature_low(self) -> float | None:
        """Return the cached low target temperature."""
        value = self._state_cache.get(ATTR_TARGET_TEMP_LOW)
        return None if value is None else float(value)

    @property
    @override
    def target_temperature_step(self) -> float | None:
        """Return the cached target temperature step."""
        value = self._state_cache.get(ATTR_TARGET_TEMP_STEP)
        return None if value is None else float(value)

    @property
    @override
    def current_humidity(self) -> float | None:
        """Return the cached current humidity."""
        value = self._state_cache.get(ATTR_CURRENT_HUMIDITY)
        return None if value is None else float(value)

    @property
    @override
    def target_humidity(self) -> float | None:
        """Return the cached target humidity."""
        value = self._state_cache.get(ATTR_HUMIDITY)
        return None if value is None else float(value)

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the cached fan mode."""
        return self._state_cache.get(ATTR_FAN_MODE)

    @property
    @override
    def fan_modes(self) -> list[str] | None:
        """Return advertised fan modes."""
        return self.description.capabilities.get(ATTR_FAN_MODES)

    @property
    @override
    def swing_mode(self) -> str | None:
        """Return the cached swing mode."""
        return self._state_cache.get(ATTR_SWING_MODE)

    @property
    @override
    def swing_modes(self) -> list[str] | None:
        """Return advertised swing modes."""
        return self.description.capabilities.get(ATTR_SWING_MODES)

    @property
    @override
    def swing_horizontal_mode(self) -> str | None:
        """Return the cached horizontal swing mode."""
        return self._state_cache.get(ATTR_SWING_HORIZONTAL_MODE)

    @property
    @override
    def swing_horizontal_modes(self) -> list[str] | None:
        """Return advertised horizontal swing modes."""
        return self.description.capabilities.get(ATTR_SWING_HORIZONTAL_MODES)

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the cached preset mode."""
        return self._state_cache.get(ATTR_PRESET_MODE)

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return advertised preset modes."""
        return self.description.capabilities.get(ATTR_PRESET_MODES)

    @property
    @override
    def min_temp(self) -> float:
        """Return the cached minimum temperature."""
        value = self.description.capabilities.get(ATTR_MIN_TEMP)
        return float(value) if value is not None else super().min_temp

    @property
    @override
    def max_temp(self) -> float:
        """Return the cached maximum temperature."""
        value = self.description.capabilities.get(ATTR_MAX_TEMP)
        return float(value) if value is not None else super().max_temp

    @property
    @override
    def min_humidity(self) -> float:
        """Return the cached minimum humidity."""
        value = self.description.capabilities.get(ATTR_MIN_HUMIDITY)
        return float(value) if value is not None else super().min_humidity

    @property
    @override
    def max_humidity(self) -> float:
        """Return the cached maximum humidity."""
        value = self.description.capabilities.get(ATTR_MAX_HUMIDITY)
        return float(value) if value is not None else super().max_humidity

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward set_temperature."""
        await self._call_service("set_temperature", **kwargs)

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Forward set_humidity."""
        await self._call_service("set_humidity", humidity=humidity)

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Forward set_fan_mode."""
        await self._call_service("set_fan_mode", fan_mode=fan_mode)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Forward set_hvac_mode."""
        await self._call_service("set_hvac_mode", hvac_mode=hvac_mode)

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Forward set_swing_mode."""
        await self._call_service("set_swing_mode", swing_mode=swing_mode)

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Forward set_swing_horizontal_mode."""
        await self._call_service(
            "set_swing_horizontal_mode", swing_horizontal_mode=swing_horizontal_mode
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode."""
        await self._call_service("set_preset_mode", preset_mode=preset_mode)

    @override
    async def async_turn_on(self) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on")

    @override
    async def async_turn_off(self) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off")

    @override
    async def async_toggle(self) -> None:
        """Forward toggle."""
        await self._call_service("toggle")
