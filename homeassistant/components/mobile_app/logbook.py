"""Describe mobile_app logbook events."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.event_type import EventType

from .const import DOMAIN

IOS_EVENT_ZONE_ENTERED = "ios.zone_entered"
IOS_EVENT_ZONE_EXITED = "ios.zone_exited"

ATTR_ZONE = "zone"
ATTR_SOURCE_DEVICE_NAME = "sourceDeviceName"
ATTR_SOURCE_DEVICE_ID = "sourceDeviceID"
EVENT_TO_DESCRIPTION: dict[EventType[Any] | str, str] = {
    IOS_EVENT_ZONE_ENTERED: "entered zone",
    IOS_EVENT_ZONE_EXITED: "exited zone",
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_zone_event(event: Event) -> dict[str, str]:
        """Describe mobile_app logbook event."""
        data = event.data
        event_description = EVENT_TO_DESCRIPTION[event.event_type]
        zone_entity_id = data.get(ATTR_ZONE)
        source_device_name = data.get(
            ATTR_SOURCE_DEVICE_NAME, data.get(ATTR_SOURCE_DEVICE_ID)
        )
        zone_name = None
        zone_icon = None
        if zone_entity_id and (zone_state := hass.states.get(zone_entity_id)):
            zone_name = zone_state.attributes.get(ATTR_FRIENDLY_NAME)
            zone_icon = zone_state.attributes.get(ATTR_ICON)
        description = {
            LOGBOOK_ENTRY_NAME: source_device_name,
            LOGBOOK_ENTRY_MESSAGE: f"{event_description} {zone_name or zone_entity_id}",
            LOGBOOK_ENTRY_ICON: zone_icon or "mdi:crosshairs-gps",
        }
        if zone_entity_id:
            description[LOGBOOK_ENTRY_ENTITY_ID] = zone_entity_id
        return description

    async_describe_event(DOMAIN, IOS_EVENT_ZONE_ENTERED, async_describe_zone_event)
    async_describe_event(DOMAIN, IOS_EVENT_ZONE_EXITED, async_describe_zone_event)
