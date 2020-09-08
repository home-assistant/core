"""Offer event listening automation rules."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

# mypy: allow-untyped-defs

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_DATA = "event_data"

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "event",
        vol.Required(CONF_EVENT_TYPE): cv.string,
        vol.Optional(CONF_EVENT_DATA): dict,
    }
)


async def async_attach_trigger(
    hass, config, action, automation_info, *, platform_type="event"
):
    """Listen for events based on configuration."""
    event_type = config.get(CONF_EVENT_TYPE)
    event_data_schema = (
        vol.Schema(config.get(CONF_EVENT_DATA), extra=vol.ALLOW_EXTRA)
        if config.get(CONF_EVENT_DATA)
        else None
    )

    @callback
    def handle_event(event):
        """Listen for events and calls the action when data matches."""
        if event_data_schema:
            # Check that the event data matches the configured
            # schema if one was provided
            try:
                event_data_schema(event.data)
            except vol.Invalid:
                # If event data doesn't match requested schema, skip event
                return

        hass.async_run_job(
            action,
            {
                "trigger": {
                    "platform": platform_type,
                    "event": event,
                    "description": f"event '{event.event_type}'",
                }
            },
            event.context,
        )

    return hass.bus.async_listen(event_type, handle_event)
