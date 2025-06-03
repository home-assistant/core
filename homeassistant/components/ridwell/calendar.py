"""Support for Ridwell calendars."""

from __future__ import annotations

import datetime

from aioridwell.model import RidwellAccount, RidwellPickupEvent

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RidwellDataUpdateCoordinator
from .entity import RidwellEntity


@callback
def async_get_calendar_event_from_pickup_event(
    pickup_event: RidwellPickupEvent,
) -> CalendarEvent:
    """Get a HASS CalendarEvent from an aioridwell PickupEvent."""
    pickup_type_string = ", ".join(
        [
            f"{pickup.name} (quantity: {pickup.quantity})"
            for pickup in pickup_event.pickups
        ]
    )
    return CalendarEvent(
        summary=f"Ridwell Pickup ({pickup_event.state.value})",
        description=f"Pickup types: {pickup_type_string}",
        start=pickup_event.pickup_date,
        end=pickup_event.pickup_date + datetime.timedelta(days=1),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ridwell calendars based on a config entry."""
    coordinator: RidwellDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RidwellCalendar(coordinator, account)
        for account in coordinator.accounts.values()
    )


class RidwellCalendar(RidwellEntity, CalendarEntity):
    """Define a Ridwell calendar."""

    _attr_name = None
    _attr_translation_key = "calendar"

    def __init__(
        self, coordinator: RidwellDataUpdateCoordinator, account: RidwellAccount
    ) -> None:
        """Initialize the Ridwell entity."""
        super().__init__(coordinator, account)

        self._attr_unique_id = self._account.account_id
        self._event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return async_get_calendar_event_from_pickup_event(self.next_pickup_event)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            async_get_calendar_event_from_pickup_event(event)
            for event in self.coordinator.data[self._account.account_id]
        ]
