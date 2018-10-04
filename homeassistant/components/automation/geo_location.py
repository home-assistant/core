"""
Offer geo location automation rules.

For more details about this automation trigger, please refer to the
documentation at
https://home-assistant.io/docs/automation/trigger/#geo-location-trigger
"""
import fnmatch
import re

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_EVENT, CONF_ENTITY_ID, CONF_ZONE, CONF_PLATFORM, EVENT_STATE_CHANGED)
from homeassistant.helpers import (
    condition, config_validation as cv)

EVENT_ENTER = 'enter'
EVENT_LEAVE = 'leave'
DEFAULT_EVENT = EVENT_ENTER

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'geo_location',
    vol.Required(CONF_ENTITY_ID): cv.string,
    vol.Required(CONF_ZONE): cv.entity_id,
    vol.Required(CONF_EVENT, default=DEFAULT_EVENT):
        vol.Any(EVENT_ENTER, EVENT_LEAVE),
})


async def async_trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID).lower()
    zone_entity_id = config.get(CONF_ZONE)
    trigger_event = config.get(CONF_EVENT)

    @callback
    def state_change_listener(event):
        """Handle specific state changes."""
        # Check if the event's entity id matches any wildcard definition.
        if not re.compile(fnmatch.translate(entity_id)).match(
                event.data.get('entity_id')):
            return

        zone_state = hass.states.get(zone_entity_id)
        from_state = event.data.get('old_state')
        from_match = condition.zone(hass, zone_state, from_state)
        to_state = event.data.get('new_state')
        to_match = condition.zone(hass, zone_state, to_state)

        # pylint: disable=too-many-boolean-expressions
        if trigger_event == EVENT_ENTER and not from_match and to_match or \
           trigger_event == EVENT_LEAVE and from_match and not to_match:
            hass.async_run_job(action({
                'trigger': {
                    'platform': 'geo_location',
                    'entity_id': event.data.get('entity_id'),
                    'from_state': from_state,
                    'to_state': to_state,
                    'zone': zone_state,
                    'event': trigger_event,
                },
            }, context=None if not to_state else to_state.context))

    return hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)
