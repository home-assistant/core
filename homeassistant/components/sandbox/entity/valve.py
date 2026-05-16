"""Sandbox proxy for valve entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxValveEntity(SandboxProxyEntity, ValveEntity):
    """Proxy for a valve entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy valve entity."""
        super().__init__(description, manager)
        self._attr_supported_features = ValveEntityFeature(
            description.supported_features
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "closed"

    @property
    def is_opening(self) -> bool | None:
        """Return if the valve is opening."""
        return self._state_cache.get("is_opening")

    @property
    def is_closing(self) -> bool | None:
        """Return if the valve is closing."""
        return self._state_cache.get("is_closing")

    @property
    def current_valve_position(self) -> int | None:
        """Return the current valve position."""
        return self._state_cache.get("current_valve_position")

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Forward open_valve to sandbox."""
        await self._forward_method("async_open_valve", **kwargs)

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Forward close_valve to sandbox."""
        await self._forward_method("async_close_valve", **kwargs)

    async def async_stop_valve(self, **kwargs: Any) -> None:
        """Forward stop_valve to sandbox."""
        await self._forward_method("async_stop_valve", **kwargs)

    async def async_set_valve_position(self, position: int) -> None:
        """Forward set_valve_position to sandbox."""
        await self._forward_method("async_set_valve_position", position=position)
