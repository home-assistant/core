"""Offer Home Assistant core automation rules."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_EVENT, CONF_PLATFORM, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback

# mypy: allow-untyped-defs

EVENT_START = "start"
EVENT_SHUTDOWN = "shutdown"
_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "homeassistant",
        vol.Required(CONF_EVENT): vol.Any(EVENT_START, EVENT_SHUTDOWN),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for events based on configuration."""
    event = config.get(CONF_EVENT)

    if event == EVENT_SHUTDOWN:

        @callback
        def hass_shutdown(event):
            """Execute when Home Assistant is shutting down."""
            hass.async_run_job(
                action,
                {"trigger": {"platform": "homeassistant", "event": event}},
                event.context,
            )

        return hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hass_shutdown)

    # Automation are enabled while hass is starting up, fire right away
    # Check state because a config reload shouldn't trigger it.
    if automation_info["home_assistant_start"]:
        hass.async_run_job(
            action({"trigger": {"platform": "homeassistant", "event": event}})
        )

    return lambda: None
