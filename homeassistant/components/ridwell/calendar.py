"""Support for Ridwell calendars."""

from __future__ import annotations

import datetime

from aioridwell.model import PickupCategory, RidwellAccount, RidwellPickupEvent

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CALENDAR_TITLE_NONE,
    CALENDAR_TITLE_ROTATING,
    CALENDAR_TITLE_STATUS,
    CONF_CALENDAR_TITLE,
    DOMAIN,
)
from .coordinator import RidwellDataUpdateCoordinator
from .entity import RidwellEntity


@callback
def async_get_calendar_event_from_pickup_event(
    pickup_event: RidwellPickupEvent, config_entry: ConfigEntry
) -> CalendarEvent:
    """Get a HASS CalendarEvent from an aioridwell PickupEvent."""
    pickup_items = []
    rotating_category = ""
    calendar_preference = config_entry.options.get(CONF_CALENDAR_TITLE, False)
    for pickup in pickup_event.pickups:
        pickup_items.append(f"{pickup.name} (quantity: {pickup.quantity})")
        if pickup.category == PickupCategory.ROTATING:
            rotating_category = pickup.name

    pickup_type_string = ", ".join(pickup_items)
    pickup_event_state = pickup_event.state.value
    summary_base = "Ridwell Pickup"

    if calendar_preference == CALENDAR_TITLE_STATUS:
        # Use state of pickup_event (e.g., scheduled, skipped, notified, etc).
        summary = f"{summary_base} ({pickup_event_state})"
    elif calendar_preference == CALENDAR_TITLE_ROTATING:
        # Use name of Rotating Category for the pickup_event.
        if rotating_category:
            summary = f"{summary_base} ({rotating_category})"
        else:
            summary = f"{summary_base} (not yet opted in/out)"
    elif calendar_preference == CALENDAR_TITLE_NONE:
        # Include only a basic title for the event.
        summary = summary_base
    else:
        summary = f"{summary_base} (Error)"

    return CalendarEvent(
        summary=summary,
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
        return async_get_calendar_event_from_pickup_event(
            self.next_pickup_event, self.coordinator.config_entry
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            async_get_calendar_event_from_pickup_event(
                event, self.coordinator.config_entry
            )
            for event in self.coordinator.data[self._account.account_id]
        ]
