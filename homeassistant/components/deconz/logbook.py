"""Describe deCONZ logbook events."""

from homeassistant.const import ATTR_DEVICE_ID, CONF_EVENT
from homeassistant.core import callback

from .const import DOMAIN as DECONZ_DOMAIN
from .deconz_event import CONF_DECONZ_EVENT
from .device_trigger import _get_deconz_event_from_device_id


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_deconz_event(event):
        """Describe deCONZ logbook event."""
        deconz_event = _get_deconz_event_from_device_id(
            hass, event.data[ATTR_DEVICE_ID]
        )

        return {
            "name": f"{deconz_event.device.name}",
            "message": f"'{event.data[CONF_EVENT]}' was fired.",
        }

    async_describe_event(DECONZ_DOMAIN, CONF_DECONZ_EVENT, async_describe_deconz_event)
