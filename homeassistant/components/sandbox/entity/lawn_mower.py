"""Sandbox proxy for ``lawn_mower`` entities."""

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxLawnMowerEntity(SandboxProxyEntity, LawnMowerEntity):
    """Proxy for a ``lawn_mower`` entity in a sandbox."""

    _features_flag = LawnMowerEntityFeature

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the cached mowing activity."""
        value = self._state_cache.get("state")
        if value is None or value == "unavailable":
            return None
        try:
            return LawnMowerActivity(value)
        except ValueError:
            return None

    async def async_start_mowing(self) -> None:
        """Forward start_mowing."""
        await self._call_service("start_mowing")

    async def async_dock(self) -> None:
        """Forward dock."""
        await self._call_service("dock")

    async def async_pause(self) -> None:
        """Forward pause."""
        await self._call_service("pause")
