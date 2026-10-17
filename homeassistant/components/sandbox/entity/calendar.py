"""Sandbox proxy for ``calendar`` entities."""

import datetime
from typing import Any, override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from . import SandboxProxyEntity


def _parse_calendar_date(value: Any) -> datetime.date | datetime.datetime | Any:
    """Parse an ISO date/datetime string back into a date or datetime."""
    if isinstance(value, str):
        if "T" in value:
            return datetime.datetime.fromisoformat(value)
        return datetime.date.fromisoformat(value)
    return value


def _calendar_event_from_dict(data: dict[str, Any]) -> CalendarEvent:
    """Rebuild a :class:`CalendarEvent` from a ``get_events`` response entry."""
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
    """Proxy for a ``calendar`` entity in a sandbox."""

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return ``None`` — the next-event listing is not proxied yet."""
        return None

    @override
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

    @override
    async def async_create_event(self, **kwargs: Any) -> None:
        """Forward create as ``calendar.create_event``."""
        await self._call_service("create_event", **kwargs)

    @override
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

    @override
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
