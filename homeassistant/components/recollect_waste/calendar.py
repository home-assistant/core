"""Support for ReCollect Waste calendars."""
from __future__ import annotations

import datetime
from typing import Any

from aiorecollect.client import PickupEvent

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import ReCollectWasteEntity
from .util import async_get_pickup_type_names


@callback
def async_get_calendar_event_from_pickup_event(
    entry: ConfigEntry, pickup_event: PickupEvent
) -> CalendarEvent:
    """Get a HASS CalendarEvent from an aiorecollect PickupEvent."""
    pickup_type_string = ", ".join(
        async_get_pickup_type_names(entry, pickup_event.pickup_types)
    )
    return CalendarEvent(
        summary="ReCollect Waste Pickup",
        description=f"Pickup types: {pickup_type_string}",
        location=pickup_event.area_name,
        start=pickup_event.date,
        end=pickup_event.date + datetime.timedelta(days=1),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ReCollect Waste sensors based on a config entry."""
    coordinator: DataUpdateCoordinator[list[PickupEvent]] = hass.data[DOMAIN][
        entry.entry_id
    ]

    async_add_entities([ReCollectWasteCalendar(hass, coordinator, entry)])


class ReCollectWasteCalendar(ReCollectWasteEntity, CalendarEntity):
    """Define a ReCollect Waste calendar."""

    _attr_icon = "mdi:delete-empty"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator[list[PickupEvent]],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the ReCollect Waste entity."""
        super().__init__(coordinator, entry)

        @callback
        def update_state(*_: Any) -> None:
            """Update the entity state.

            This exists to force update the calendar state regularly, regardless of when
            the coordinator last received data. We do this to ensure the entity will
            update near the start of a pickup event.
            """
            self.async_write_ha_state()

        entry.async_on_unload(
            async_track_time_interval(
                hass,
                update_state,
                datetime.timedelta(minutes=1),
            )
        )

        self._attr_unique_id = self._identifier
        self._event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            current_event = next(
                event
                for event in self.coordinator.data
                if event.date >= datetime.date.today()
            )
        except StopIteration:
            self._event = None
        else:
            self._event = async_get_calendar_event_from_pickup_event(
                self._entry, current_event
            )

        super()._handle_coordinator_update()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            async_get_calendar_event_from_pickup_event(self._entry, event)
            for event in self.coordinator.data
        ]
