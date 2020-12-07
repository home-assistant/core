"""Describe logbook events."""

from homeassistant.const import CONF_DEVICE, CONF_DEVICE_ID
from homeassistant.core import callback

from .const import ATTR_CHANNEL, ATTR_CLICK_TYPE, DOMAIN, EVENT_SHELLY_CLICK
from .utils import get_device_name, get_device_wrapper


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        wrapper = get_device_wrapper(hass, event.data[CONF_DEVICE_ID])
        if wrapper:
            device_name = get_device_name(wrapper.device)
        else:
            device_name = event.data[CONF_DEVICE]

        channel = event.data[ATTR_CHANNEL]
        click_type = event.data[ATTR_CLICK_TYPE]

        return {
            "name": "Shelly",
            "message": f"'{click_type}' click event for {device_name} channel {channel} was fired.",
        }

    async_describe_event(DOMAIN, EVENT_SHELLY_CLICK, async_describe_logbook_event)
