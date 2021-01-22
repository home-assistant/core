"""Describe deCONZ logbook events."""

from typing import Callable, Optional

from homeassistant.const import ATTR_DEVICE_ID, CONF_EVENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import Event

from .const import DOMAIN as DECONZ_DOMAIN
from .deconz_event import CONF_DECONZ_EVENT, DeconzEvent
from .device_trigger import _get_deconz_event_from_device_id


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_deconz_event(event: Event) -> dict:
        """Describe deCONZ logbook event."""
        deconz_event: Optional[DeconzEvent] = _get_deconz_event_from_device_id(
            hass, event.data[ATTR_DEVICE_ID]
        )

        return {
            "name": f"{deconz_event.device.name}",
            "message": f"fired event '{event.data[CONF_EVENT]}'.",
        }

    async_describe_event(DECONZ_DOMAIN, CONF_DECONZ_EVENT, async_describe_deconz_event)
