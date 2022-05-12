"""Describe homeassistant logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback

from . import DOMAIN

EVENT_TO_NAME = {
    EVENT_HOMEASSISTANT_STOP: "stopped",
    EVENT_HOMEASSISTANT_START: "started",
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_hass_event(event: Event) -> dict[str, str]:
        """Describe homeassisant logbook event."""
        return {"name": "Home Assistant", "message": EVENT_TO_NAME[event.event_type]}

    async_describe_event(DOMAIN, EVENT_HOMEASSISTANT_STOP, async_describe_hass_event)
    async_describe_event(DOMAIN, EVENT_HOMEASSISTANT_START, async_describe_hass_event)
