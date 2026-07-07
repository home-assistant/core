"""Sandbox proxy for ``switch`` entities."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSwitchEntity(SandboxProxyEntity, SwitchEntity):
    """Proxy for a ``switch`` entity in a sandbox."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the cached state is ``on``."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on as a ``switch.turn_on`` service call."""
        await self._call_service("turn_on", **kwargs)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off as a ``switch.turn_off`` service call."""
        await self._call_service("turn_off", **kwargs)

    @override
    async def async_toggle(self, **kwargs: Any) -> None:
        """Forward toggle as a ``switch.toggle`` service call."""
        await self._call_service("toggle", **kwargs)
