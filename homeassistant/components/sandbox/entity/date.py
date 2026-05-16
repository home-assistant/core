"""Sandbox proxy for date entities."""

from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity

from . import SandboxProxyEntity


class SandboxDateEntity(SandboxProxyEntity, DateEntity):
    """Proxy for a date entity in a sandbox."""

    @property
    def native_value(self):
        """Return the current date value."""
        val = self._state_cache.get("state")
        if val is None:
            return None
        if isinstance(val, str):
            return date.fromisoformat(val)
        return val

    async def async_set_value(self, value) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value.isoformat())
