"""Sandbox v2 proxy for ``calendar`` entities."""

from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxCalendarEntity(SandboxProxyEntity, CalendarEntity):
    """Proxy for a ``calendar`` entity in a sandbox.

    Calendar service calls go through the standard ``calendar.*`` service
    handlers; the listing/iteration APIs are server-side queries we don't
    proxy in Phase 13 (no test infra exercises them yet).
    """

    @property
    def event(self) -> CalendarEvent | None:
        """Return ``None`` — listings are only fetched through service calls."""
        return None

    async def async_get_events(
        self, hass: Any, start_date: Any, end_date: Any
    ) -> list[CalendarEvent]:
        """No-op — listing happens via the sandbox-side service handler."""
        return []

    async def async_create_event(self, **kwargs: Any) -> None:
        """Forward create as ``calendar.create_event``."""
        await self._call_service("create_event", **kwargs)
