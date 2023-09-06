"""Calendar platform for a Epic Games Store."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EGSUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    coordinator: EGSUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entity = EGSCalendar(coordinator, entry.entry_id)
    async_add_entities([entity], True)


class EGSCalendar(CalendarEntity):
    """A calendar entity by Epic Games Store."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EGSUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize EGSCalendar."""
        self._coordinator = coordinator
        self._event: CalendarEvent | None = None
        self._attr_name = "Epic Games Store Free Games"
        self._attr_unique_id = unique_id

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    @property  # type: ignore[misc]
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the entity state attributes."""
        return {**(super().state_attributes or {}), **self._coordinator.data}

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events = self._coordinator.data.values()
        return [_get_calendar_event(event) for event in events]

    async def async_update(self) -> None:
        """Update entity state with the next upcoming event."""
        event = self._coordinator.data.get("free_games") or self._coordinator.data.get(
            "next_free_games"
        )
        if event:
            self._event = _get_calendar_event(event)


def _get_calendar_event(event: dict[str, Any]) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    return CalendarEvent(
        summary=(
            "Current"
            if event["start_at"]
            <= datetime.now().replace(tzinfo=ZoneInfo("UTC"))
            < event["end_at"]
            else "Upcoming"
        )
        + " free games",
        start=event["start_at"],
        end=event["end_at"],
        description="\n\n\n".join(
            [
                f"- {game['title']} : \n{game['description']}\n\n{game['url']}"
                for game in event["games"]
            ]
        ),
    )
