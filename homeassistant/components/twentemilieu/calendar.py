"""Support for Twente Milieu Calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import TwenteMilieuConfigEntry
from .const import WASTE_TYPE_TO_DESCRIPTION
from .entity import TwenteMilieuEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TwenteMilieuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twente Milieu calendar based on a config entry."""
    async_add_entities([TwenteMilieuCalendar(entry)])


class TwenteMilieuCalendar(TwenteMilieuEntity, CalendarEntity):
    """Defines a Twente Milieu calendar."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "calendar"

    def __init__(self, entry: TwenteMilieuConfigEntry) -> None:
        """Initialize the Twente Milieu entity."""
        super().__init__(entry)
        self._attr_unique_id = str(entry.data[CONF_ID])
        self._event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events: list[CalendarEvent] = []
        for waste_type, waste_dates in self.coordinator.data.items():
            events.extend(
                CalendarEvent(
                    summary=WASTE_TYPE_TO_DESCRIPTION[waste_type],
                    start=waste_date,
                    end=waste_date + timedelta(days=1),
                )
                for waste_date in waste_dates
                if start_date.date() <= waste_date <= end_date.date()
            )

        return events

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        next_waste_pickup_type = None
        next_waste_pickup_date = None
        for waste_type, waste_dates in self.coordinator.data.items():
            if (
                waste_dates
                and (
                    next_waste_pickup_date is None
                    or waste_dates[0]  # type: ignore[unreachable]
                    < next_waste_pickup_date
                )
                and waste_dates[0] >= dt_util.now().date()
            ):
                next_waste_pickup_date = waste_dates[0]
                next_waste_pickup_type = waste_type

        self._event = None
        if next_waste_pickup_date is not None and next_waste_pickup_type is not None:
            self._event = CalendarEvent(
                summary=WASTE_TYPE_TO_DESCRIPTION[next_waste_pickup_type],
                start=next_waste_pickup_date,
                end=next_waste_pickup_date + timedelta(days=1),
            )

        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
