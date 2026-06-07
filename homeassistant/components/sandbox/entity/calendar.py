"""Sandbox proxy for ``calendar`` entities."""

from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from . import SandboxProxyEntity, raise_not_proxied


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxCalendarEntity(SandboxProxyEntity, CalendarEntity):
    """Proxy for a ``calendar`` entity in a sandbox.

    ``create_event`` forwards through the standard ``calendar.create_event``
    service. The listing/iteration query (``async_get_events``, also driving
    the ``calendar/event/subscribe`` WS command) and the WS-only event edits
    (``calendar/event/update`` / ``delete``) are server-side queries the
    entity-method bridge can't express yet, so they raise rather than silently
    returning empty results. See ``sandbox/docs/query-shaped-rpcs.md``.
    """

    @property
    def event(self) -> CalendarEvent | None:
        """Return ``None`` — the next-event listing is not proxied yet."""
        return None

    async def async_get_events(
        self, hass: Any, start_date: Any, end_date: Any
    ) -> list[CalendarEvent]:
        """Raise — calendar listing is a server-side query, not yet proxied."""
        raise_not_proxied("Listing calendar events")

    async def async_create_event(self, **kwargs: Any) -> None:
        """Forward create as ``calendar.create_event``."""
        await self._call_service("create_event", **kwargs)

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Raise — ``calendar/event/update`` is WS-only, not yet proxied."""
        raise_not_proxied("Updating a calendar event")

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Raise — ``calendar/event/delete`` is WS-only, not yet proxied."""
        raise_not_proxied("Deleting a calendar event")
