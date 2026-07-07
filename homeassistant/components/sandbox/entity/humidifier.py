"""Sandbox proxy for ``humidifier`` entities."""

from typing import override

from homeassistant.components.humidifier import (
    ATTR_ACTION,
    ATTR_AVAILABLE_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_MODE,
    HumidifierAction,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxHumidifierEntity(SandboxProxyEntity, HumidifierEntity):
    """Proxy for a ``humidifier`` entity in a sandbox."""

    _features_flag = HumidifierEntityFeature

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON

    @property
    @override
    def action(self) -> HumidifierAction | None:
        """Return the cached current action."""
        value = self._state_cache.get(ATTR_ACTION)
        if value is None:
            return None
        try:
            return HumidifierAction(value)
        except ValueError:
            return None

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
    def mode(self) -> str | None:
        """Return the cached mode."""
        return self._state_cache.get(ATTR_MODE)

    @property
    @override
    def available_modes(self) -> list[str] | None:
        """Return the configured available modes."""
        modes = self.description.capabilities.get(ATTR_AVAILABLE_MODES)
        return list(modes) if modes else None

    @property
    @override
    def min_humidity(self) -> float:
        """Return the configured minimum humidity."""
        value = self.description.capabilities.get(ATTR_MIN_HUMIDITY)
        return float(value) if value is not None else super().min_humidity

    @property
    @override
    def max_humidity(self) -> float:
        """Return the configured maximum humidity."""
        value = self.description.capabilities.get(ATTR_MAX_HUMIDITY)
        return float(value) if value is not None else super().max_humidity

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on")

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off")

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Forward set_humidity."""
        await self._call_service("set_humidity", humidity=humidity)

    @override
    async def async_set_mode(self, mode: str) -> None:
        """Forward set_mode."""
        await self._call_service("set_mode", mode=mode)
