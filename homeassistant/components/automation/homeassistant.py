"""
Offer Home Assistant core automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#homeassistant-trigger
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback, CoreState
from homeassistant.const import (
    CONF_PLATFORM, CONF_EVENT, EVENT_HOMEASSISTANT_STOP)

EVENT_START = 'start'
EVENT_SHUTDOWN = 'shutdown'
_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'homeassistant',
    vol.Required(CONF_EVENT): vol.Any(EVENT_START, EVENT_SHUTDOWN),
})


@asyncio.coroutine
def async_trigger(hass, config, action):
    """Listen for events based on configuration."""
    event = config.get(CONF_EVENT)

    if event == EVENT_SHUTDOWN:
        @callback
        def hass_shutdown(event):
            """Execute when Home Assistant is shutting down."""
            hass.async_run_job(action({
                'trigger': {
                    'platform': 'homeassistant',
                    'event': event,
                },
            }, context=event.context))

        return hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                          hass_shutdown)

    # Automation are enabled while hass is starting up, fire right away
    # Check state because a config reload shouldn't trigger it.
    if hass.state == CoreState.starting:
        hass.async_run_job(action({
            'trigger': {
                'platform': 'homeassistant',
                'event': event,
            },
        }))

    return lambda: None
