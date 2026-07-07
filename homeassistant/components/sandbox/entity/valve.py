"""Sandbox proxy for ``valve`` entities."""

from typing import TYPE_CHECKING

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_IS_CLOSED,
    ValveEntity,
    ValveEntityFeature,
    ValveState,
)

from . import SandboxProxyEntity

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxValveEntity(SandboxProxyEntity, ValveEntity):
    """Proxy for a ``valve`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``ValveEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = ValveEntityFeature(
            description.supported_features or 0
        )

    @property
    def reports_position(self) -> bool:
        """Mirror the sandbox-side flag."""
        return bool(self.description.capabilities.get("reports_position", False))

    @property
    def is_opening(self) -> bool | None:
        """True iff cached state is ``opening``."""
        return self._state_cache.get("state") == ValveState.OPENING

    @property
    def is_closing(self) -> bool | None:
        """True iff cached state is ``closing``."""
        return self._state_cache.get("state") == ValveState.CLOSING

    @property
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
    def current_valve_position(self) -> int | None:
        """Return the cached current position."""
        value = self._state_cache.get(ATTR_CURRENT_POSITION)
        return None if value is None else int(value)

    async def async_open_valve(self) -> None:
        """Forward open_valve."""
        await self._call_service("open_valve")

    async def async_close_valve(self) -> None:
        """Forward close_valve."""
        await self._call_service("close_valve")

    async def async_set_valve_position(self, position: int) -> None:
        """Forward set_valve_position."""
        await self._call_service("set_valve_position", position=position)

    async def async_stop_valve(self) -> None:
        """Forward stop_valve."""
        await self._call_service("stop_valve")
