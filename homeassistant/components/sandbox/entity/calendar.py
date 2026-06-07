"""Sandbox proxy for ``calendar`` entities."""

import datetime
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from . import SandboxProxyEntity


def _parse_calendar_date(value: Any) -> datetime.date | datetime.datetime | Any:
    """Parse an ISO date/datetime string back into a date or datetime.

    The ``calendar.get_events`` service serialises every event date through
    ``CalendarEvent.as_dict``'s factory, which emits ``isoformat()`` strings.
    All-day events carry a bare ``YYYY-MM-DD`` (a ``date``); timed events carry
    a full timestamp (a ``datetime``). ``CalendarEvent`` keys its all-day check
    off the start being a plain ``date``, so the two must rebuild distinctly.
    """
    if isinstance(value, str):
        if "T" in value:
            return datetime.datetime.fromisoformat(value)
        return datetime.date.fromisoformat(value)
    return value


def _calendar_event_from_dict(data: dict[str, Any]) -> CalendarEvent:
    """Rebuild a :class:`CalendarEvent` from a ``get_events`` response entry.

    ``CalendarEvent`` is a dataclass whose ``as_dict`` shape uses the field
    names directly, so fields map across explicitly (no ``**data`` splat — the
    response also carries the derived ``all_day`` key the constructor rejects).
    ``get_events`` only returns start/end/summary/description/location; the
    uid/recurrence_id/rrule keys are read defensively in case a richer payload
    arrives.
    """
    return CalendarEvent(
        start=_parse_calendar_date(data["start"]),
        end=_parse_calendar_date(data["end"]),
        summary=data["summary"],
        description=data.get("description"),
        location=data.get("location"),
        uid=data.get("uid"),
        recurrence_id=data.get("recurrence_id"),
        rrule=data.get("rrule"),
    )


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxCalendarEntity(SandboxProxyEntity, CalendarEntity):
    """Proxy for a ``calendar`` entity in a sandbox.

    ``create_event`` forwards through the standard ``calendar.create_event``
    service. The listing query (``async_get_events``) rides the
    ``calendar.get_events`` ``SupportsResponse`` service; the WS-only event
    edits (``calendar/event/update`` / ``delete``) cross via the generic
    ``EntityQuery`` RPC. The recurrence-timer subscription
    (``calendar/event/subscribe``) is deferred — the next/current event is not
    pushed, so ``event`` returns ``None``. See
    ``sandbox/docs/query-shaped-rpcs.md``.
    """

    @property
    def event(self) -> CalendarEvent | None:
        """Return ``None`` — the next-event listing is not proxied yet."""
        return None

    async def async_get_events(
        self, hass: Any, start_date: Any, end_date: Any
    ) -> list[CalendarEvent]:
        """Forward the listing query as the ``calendar.get_events`` service."""
        response = await self._call_service(
            "get_events",
            return_response=True,
            start_date_time=start_date.isoformat(),
            end_date_time=end_date.isoformat(),
        )
        entity_response = response.get(self.description.sandbox_entity_id, {})
        return [
            _calendar_event_from_dict(event)
            for event in entity_response.get("events", [])
        ]

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
        """Forward the WS-only event update through ``EntityQuery``."""
        await self._entity_query(
            "async_update_event",
            uid=uid,
            event=event,
            recurrence_id=recurrence_id,
            recurrence_range=recurrence_range,
        )

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Forward the WS-only event delete through ``EntityQuery``."""
        await self._entity_query(
            "async_delete_event",
            uid=uid,
            recurrence_id=recurrence_id,
            recurrence_range=recurrence_range,
        )
