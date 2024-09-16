"""Jewish Calendar calendar platform."""

from datetime import UTC, datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import JewishCalendarEntity

CALENDAR_TYPES: tuple[EntityDescription, ...] = (
    EntityDescription(
        key="events",
        name="Events",
        icon="mdi:calendar",
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Jewish Calendar config entry."""
    async_add_entities(
        JewishCalendar(config_entry, description) for description in CALENDAR_TYPES
    )


class JewishCalendar(JewishCalendarEntity, CalendarEntity):
    """Representation of a Jewish Calendar element."""

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return CalendarEvent(
            start=datetime(2024, 9, 17, tzinfo=UTC),
            end=datetime(2024, 9, 18, tzinfo=UTC),
            summary="Get test to pass",
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        raise NotImplementedError
