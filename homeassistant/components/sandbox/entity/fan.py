"""Sandbox v2 proxy for ``fan`` entities."""

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxFanEntity(SandboxProxyEntity, FanEntity):
    """Proxy for a ``fan`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``FanEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = FanEntityFeature(
            description.supported_features or 0
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON

    @property
    def percentage(self) -> int | None:
        """Return the cached fan percentage."""
        value = self._state_cache.get(ATTR_PERCENTAGE)
        return None if value is None else int(value)

    @property
    def current_direction(self) -> str | None:
        """Return the cached direction."""
        return self._state_cache.get(ATTR_DIRECTION)

    @property
    def oscillating(self) -> bool | None:
        """Return the cached oscillation state."""
        value = self._state_cache.get(ATTR_OSCILLATING)
        return None if value is None else bool(value)

    @property
    def preset_mode(self) -> str | None:
        """Return the cached preset mode."""
        return self._state_cache.get(ATTR_PRESET_MODE)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the configured preset modes."""
        modes = self.description.capabilities.get(ATTR_PRESET_MODES)
        return list(modes) if modes else None

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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off", **kwargs)

    async def async_set_percentage(self, percentage: int) -> None:
        """Forward set_percentage."""
        await self._call_service("set_percentage", percentage=percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Forward set_preset_mode."""
        await self._call_service("set_preset_mode", preset_mode=preset_mode)

    async def async_set_direction(self, direction: str) -> None:
        """Forward set_direction."""
        await self._call_service("set_direction", direction=direction)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Forward oscillate."""
        await self._call_service("oscillate", oscillating=oscillating)
