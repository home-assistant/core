"""Describe bthome logbook events."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get

from .const import (
    BTHOME_BLE_EVENT,
    DOMAIN,
    BTHomeBleEvent,
)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""
    dr = async_get(hass)

    @callback
    def async_describe_bthome_event(event: Event) -> dict[str, str]:
        """Describe bthome logbook event."""
        data = event.data
        if TYPE_CHECKING:
            data = cast(BTHomeBleEvent, data)  # type: ignore[assignment]
        device = dr.async_get(data["device_id"])
        name = device and device.name or f'BTHome {data["address"]}'
        if properties := data["event_properties"]:
            message = f"{data['event_class']} {data['event_type']}: {properties}"
        else:
            message = f"{data['event_class']} {data['event_type']}"
        return {
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: message,
        }

    async_describe_event(DOMAIN, BTHOME_BLE_EVENT, async_describe_bthome_event)
