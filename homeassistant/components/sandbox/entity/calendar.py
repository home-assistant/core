"""Sandbox proxy for calendar entities."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant

from . import SandboxProxyEntity


class SandboxCalendarEntity(SandboxProxyEntity, CalendarEntity):
    """Proxy for a calendar entity in a sandbox."""

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event."""
        event_data = self._state_cache.get("event")
        if event_data is None:
            return None
        start = event_data.get("start")
        end = event_data.get("end")
        if isinstance(start, str):
            start = datetime.fromisoformat(start) if "T" in start else date.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end) if "T" in end else date.fromisoformat(end)
        return CalendarEvent(
            start=start,
            end=end,
            summary=event_data.get("summary", ""),
            description=event_data.get("description"),
            location=event_data.get("location"),
        )

    async def async_get_events(self, hass: HomeAssistant, start_date, end_date) -> list[CalendarEvent]:
        """Forward get_events to sandbox."""
        result = await self._forward_method(
            "async_get_events",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        if not result:
            return []
        events = []
        for ev in result:
            start = ev.get("start")
            end = ev.get("end")
            if isinstance(start, str):
                start = datetime.fromisoformat(start) if "T" in start else date.fromisoformat(start)
            if isinstance(end, str):
                end = datetime.fromisoformat(end) if "T" in end else date.fromisoformat(end)
            events.append(CalendarEvent(
                start=start,
                end=end,
                summary=ev.get("summary", ""),
                description=ev.get("description"),
                location=ev.get("location"),
            ))
        return events
