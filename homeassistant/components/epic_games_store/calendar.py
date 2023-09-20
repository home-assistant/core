"""Calendar platform for a Epic Games Store."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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

    entities = [
        EGSFreeGamesCalendar(coordinator, entry.entry_id),
        EGSDiscountGameCalendar(coordinator, entry.entry_id),
    ]
    async_add_entities(entities, True)


class EGSCalendar(CalendarEntity):
    """A calendar entity by Epic Games Store."""

    _attr_has_entity_name = True

    _cal_type: str = ""

    def __init__(
        self,
        coordinator: EGSUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize EGSCalendar."""
        self._coordinator = coordinator
        self._event: CalendarEvent | None = None
        self._attr_name = f"Epic Games Store {self._cal_type.title()} Games"
        self._attr_unique_id = f"{unique_id}-{self._cal_type}"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    @property  # type: ignore[misc]
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the entity state attributes."""
        return {
            **(super().state_attributes or {}),
            "games": self._coordinator.data[self._cal_type],
        }

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events: list[dict[str, Any]] = self._coordinator.data[self._cal_type]
        return [_get_calendar_event(event) for event in events]

    async def async_update(self) -> None:
        """Update entity state with the next upcoming event."""
        event: list[dict[str, Any]] = self._coordinator.data[self._cal_type]
        if event:
            self._event = _get_calendar_event(event[0])


class EGSFreeGamesCalendar(EGSCalendar):
    """A calendar of free games from the Epic Games Store."""

    _cal_type = "free"


class EGSDiscountGameCalendar(EGSCalendar):
    """A calendar of discount games from the Epic Games Store."""

    _cal_type = "discount"


def _get_calendar_event(event: dict[str, Any]) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    return CalendarEvent(
        summary=event["title"],
        start=event["discount_start_at"],
        end=event["discount_end_at"],
        description=f"{event['description']}\n\n{event['url']}",
    )
