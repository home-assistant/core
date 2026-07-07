"""Sandbox proxy for ``fan`` entities."""

from typing import Any, override

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxFanEntity(SandboxProxyEntity, FanEntity):
    """Proxy for a ``fan`` entity in a sandbox."""

    _features_flag = FanEntityFeature

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
    def percentage(self) -> int | None:
        """Return the cached fan percentage."""
        value = self._state_cache.get(ATTR_PERCENTAGE)
        return None if value is None else int(value)

    @property
    @override
    def current_direction(self) -> str | None:
        """Return the cached direction."""
        return self._state_cache.get(ATTR_DIRECTION)

    @property
    @override
    def oscillating(self) -> bool | None:
        """Return the cached oscillation state."""
        value = self._state_cache.get(ATTR_OSCILLATING)
        return None if value is None else bool(value)

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the cached preset mode."""
        return self._state_cache.get(ATTR_PRESET_MODE)

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return the configured preset modes."""
        modes = self.description.capabilities.get(ATTR_PRESET_MODES)
        return list(modes) if modes else None

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Forward turn_on."""
        payload: dict[str, Any] = dict(kwargs)
        if percentage is not None:
            payload[ATTR_PERCENTAGE] = percentage
        if preset_mode is not None:
            payload[ATTR_PRESET_MODE] = preset_mode
        await self._call_service("turn_on", **payload)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off", **kwargs)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Forward set_percentage."""
        await self._call_service("set_percentage", percentage=percentage)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode."""
        await self._call_service("set_preset_mode", preset_mode=preset_mode)

    @override
    async def async_set_direction(self, direction: str) -> None:
        """Forward set_direction."""
        await self._call_service("set_direction", direction=direction)

    @override
    async def async_oscillate(self, oscillating: bool) -> None:
        """Forward oscillate."""
        await self._call_service("oscillate", oscillating=oscillating)
