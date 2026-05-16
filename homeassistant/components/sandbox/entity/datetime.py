"""Sandbox proxy for datetime entities."""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.datetime import DateTimeEntity

from . import SandboxProxyEntity


class SandboxDateTimeEntity(SandboxProxyEntity, DateTimeEntity):
    """Proxy for a datetime entity in a sandbox."""

    @property
    def native_value(self):
        """Return the current datetime value."""
        val = self._state_cache.get("state")
        if val is None:
            return None
        if isinstance(val, str):
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return val

    async def async_set_value(self, value) -> None:
        """Forward set_value to sandbox."""
        await self._forward_method("async_set_value", value=value.isoformat())
