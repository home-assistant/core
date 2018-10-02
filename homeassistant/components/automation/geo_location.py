"""
Offer geo location automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/docs/automation/trigger/#geo-location-trigger
"""
import fnmatch
import re

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_EVENT, CONF_ENTITY_ID, CONF_ZONE, CONF_PLATFORM,
    EVENT_STATE_CHANGED)
from homeassistant.helpers import (
    condition, config_validation as cv)
from homeassistant.loader import bind_hass

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
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)
    event = config.get(CONF_EVENT)

    @callback
    def zone_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        zone_state = hass.states.get(zone_entity_id)
        if from_s:
            from_match = condition.zone(hass, zone_state, from_s)
        else:
            from_match = False
        to_match = condition.zone(hass, zone_state, to_s)

        # pylint: disable=too-many-boolean-expressions
        if event == EVENT_ENTER and not from_match and to_match or \
           event == EVENT_LEAVE and from_match and not to_match:
            hass.async_run_job(action({
                'trigger': {
                    'platform': 'geo_location',
                    'entity_id': entity,
                    'from_state': from_s,
                    'to_state': to_s,
                    'zone': zone_state,
                    'event': event,
                },
            }, context=to_s.context))

    return async_track_state_change(hass, entity_id,
                                    zone_automation_listener)


@callback
@bind_hass
def async_track_state_change(hass, entity_id, action):
    """Track specific state changes."""

    # Ensure it is a lowercase list with entity ids we want to match on
    entity_id = entity_id.lower()

    @callback
    def state_change_listener(event):
        """Handle specific state changes."""
        # Check if the event's entity id matches any wildcard definition.
        if not re.compile(fnmatch.translate(entity_id)).match(
                event.data.get('entity_id')):
            return

        hass.async_run_job(action, event.data.get('entity_id'),
                           event.data.get('old_state'),
                           event.data.get('new_state'))

    return hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)
