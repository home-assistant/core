"""Offer event listening automation rules."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

# mypy: allow-untyped-defs

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_DATA = "event_data"
CONF_EVENT_CONTEXT = "context"

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "event",
        vol.Required(CONF_EVENT_TYPE): cv.string,
        vol.Optional(CONF_EVENT_DATA): dict,
        vol.Optional(CONF_EVENT_CONTEXT): dict,
    }
)


def _populate_schema(config, config_parameter):
    if config_parameter not in config:
        return None

    return vol.Schema(
        {vol.Required(key): value for key, value in config[config_parameter].items()},
        extra=vol.ALLOW_EXTRA,
    )


async def async_attach_trigger(
    hass, config, action, automation_info, *, platform_type="event"
):
    """Listen for events based on configuration."""
    event_type = config.get(CONF_EVENT_TYPE)
    event_data_schema = _populate_schema(config, CONF_EVENT_DATA)
    event_context_schema = _populate_schema(config, CONF_EVENT_CONTEXT)

    @callback
    def handle_event(event):
        """Listen for events and calls the action when data matches."""
        try:
            # Check that the event data and context match the configured
            # schema if one was provided
            if event_data_schema:
                event_data_schema(event.data)
            if event_context_schema:
                event_context_schema(event.context.as_dict())
        except vol.Invalid:
            # If event doesn't match, skip event
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
