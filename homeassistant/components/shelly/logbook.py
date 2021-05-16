"""Describe Shelly logbook events."""

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import callback

from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from .utils import get_device_name, get_device_wrapper


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_shelly_click_event(event):
        """Describe shelly.click logbook event."""
        wrapper = get_device_wrapper(hass, event.data[ATTR_DEVICE_ID])
        if wrapper:
            device_name = get_device_name(wrapper.device)
        else:
            device_name = event.data[ATTR_DEVICE]

        channel = event.data[ATTR_CHANNEL]
        click_type = event.data[ATTR_CLICK_TYPE]

        return {
            "name": "Shelly",
            "message": f"'{click_type}' click event for {device_name} channel {channel} was fired.",
        }

    async_describe_event(DOMAIN, EVENT_SHELLY_CLICK, async_describe_shelly_click_event)
