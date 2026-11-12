"""Sandbox proxy for ``valve`` entities."""

from typing import override

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_IS_CLOSED,
    ValveEntity,
    ValveEntityFeature,
    ValveState,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxValveEntity(SandboxProxyEntity, ValveEntity):
    """Proxy for a ``valve`` entity in a sandbox."""

    _features_flag = ValveEntityFeature

    @property
    @override
    def reports_position(self) -> bool:
        """Mirror the sandbox-side flag."""
        return bool(self.description.capabilities.get("reports_position", False))

    @property
    @override
    def is_opening(self) -> bool | None:
        """True iff cached state is ``opening``."""
        return self._state_cache.get("state") == ValveState.OPENING

    @property
    @override
    def is_closing(self) -> bool | None:
        """True iff cached state is ``closing``."""
        return self._state_cache.get("state") == ValveState.CLOSING

    @property
    @override
    def is_closed(self) -> bool | None:
        """Derive closed from cached state / ATTR_IS_CLOSED."""
        if (value := self._state_cache.get(ATTR_IS_CLOSED)) is not None:
            return bool(value)
        state = self._state_cache.get("state")
        if state == ValveState.CLOSED:
            return True
        if state == ValveState.OPEN:
            return False
        return None

    @property
    @override
    def current_valve_position(self) -> int | None:
        """Return the cached current position."""
        value = self._state_cache.get(ATTR_CURRENT_POSITION)
        return None if value is None else int(value)

    @override
    async def async_open_valve(self) -> None:
        """Forward open_valve."""
        await self._call_service("open_valve")

    @override
    async def async_close_valve(self) -> None:
        """Forward close_valve."""
        await self._call_service("close_valve")

    @override
    async def async_set_valve_position(self, position: int) -> None:
        """Forward set_valve_position."""
        await self._call_service("set_valve_position", position=position)

    @override
    async def async_stop_valve(self) -> None:
        """Forward stop_valve."""
        await self._call_service("stop_valve")
