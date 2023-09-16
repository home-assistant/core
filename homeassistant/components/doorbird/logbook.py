"""Describe logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN
from .models import DoorBirdData


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[Event], dict[str, str | None]]], None
    ],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event: Event) -> dict[str, str | None]:
        """Describe a logbook event."""
        return {
            LOGBOOK_ENTRY_NAME: "Doorbird",
            LOGBOOK_ENTRY_MESSAGE: f"Event {event.event_type} was fired",
            # Database entries before Jun 25th 2020 will not have an entity ID
            LOGBOOK_ENTRY_ENTITY_ID: event.data.get(ATTR_ENTITY_ID),
        }

    domain_data: dict[str, DoorBirdData] = hass.data[DOMAIN]
    for data in domain_data.values():
        for event in data.door_station.door_station_events:
            async_describe_event(
                DOMAIN, f"{DOMAIN}_{event}", async_describe_logbook_event
            )
