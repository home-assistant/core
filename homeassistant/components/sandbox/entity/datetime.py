"""Sandbox proxy for ``datetime`` entities."""

from datetime import datetime
from typing import override

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.util import dt as dt_util

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxDateTimeEntity(SandboxProxyEntity, DateTimeEntity):
    """Proxy for a ``datetime`` entity in a sandbox."""

    @property
    @override
    def native_value(self) -> datetime | None:
        """Parse the cached ISO datetime string."""
        value = self._state_cache.get("state")
        if not isinstance(value, str) or value in ("unavailable", "unknown"):
            return None
        try:
            return dt_util.parse_datetime(value)
        except TypeError, ValueError:
            return None

    @override
    async def async_set_value(self, value: datetime) -> None:
        """Forward set_value as ``datetime.set_value``."""
        await self._call_service("set_value", datetime=value.isoformat())
