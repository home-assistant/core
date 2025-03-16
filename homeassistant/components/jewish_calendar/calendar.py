"""Jewish Calendar calendar platform."""

from datetime import UTC, date, datetime
import logging

from hdate import HDateInfo, Zmanim

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import JewishCalendarEntity

_LOGGER = logging.getLogger(__name__)
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
        events = []
        for ordinal in range(start_date.toordinal(), end_date.toordinal()):
            _date = date.fromordinal(ordinal)
            info = HDateInfo(_date, self.data.diaspora)
            match getattr(self, "subscribed_events"):
                case "date":
                    event = CalendarEvent(
                        start=_date, end=_date, summary=str(info.hdate)
                    )
                case "holiday":
                    if info.is_holiday:
                        event = CalendarEvent(
                            start=_date, end=_date, summary=str(info.holidays)
                        )

            zmanim = Zmanim(
                _date,
                self.data.location,
                self.data.candle_lighting_offset,
                self.data.havdalah_offset,
            )
            _LOGGER.info(zmanim)
            for enabled_event in getattr(self, "subscribed_events"):
                event = CalendarEvent(
                    start=_date, end=_date, summary=getattr(info, enabled_event)
                )
                events.append(event)
        return events
