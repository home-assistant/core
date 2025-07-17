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

    subscribed_events: list[str]

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
        data = self.coordinator.data
        for ordinal in range(start_date.toordinal(), end_date.toordinal()):
            _date = date.fromordinal(ordinal)
            info = HDateInfo(_date, data.diaspora)
            zmanim = Zmanim(
                _date, data.location, data.candle_lighting_offset, data.havdalah_offset
            )
            _LOGGER.info(zmanim)
            for enabled_event in self.subscribed_events:
                if enabled_event == "date":
                    event = CalendarEvent(
                        start=_date, end=_date, summary=str(info.hdate)
                    )
                elif enabled_event == "holiday":
                    if info.is_holiday:
                        event = CalendarEvent(
                            start=_date, end=_date, summary=str(info.holidays)
                        )
                else:
                    event = CalendarEvent(
                        start=_date, end=_date, summary=getattr(info, enabled_event)
                    )
                events.append(event)
        return events
