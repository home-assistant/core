"""
Offer geo location automation rules.

For more details about this automation trigger, please refer to the
documentation at
https://home-assistant.io/docs/automation/trigger/#geo-location-trigger
"""
import voluptuous as vol

from homeassistant.components.geo_location import DOMAIN
from homeassistant.core import callback
from homeassistant.const import (
    CONF_EVENT, CONF_PLATFORM, CONF_SOURCE, CONF_ZONE, EVENT_STATE_CHANGED)
from homeassistant.helpers import (
    condition, config_validation as cv)
from homeassistant.helpers.config_validation import entity_domain

EVENT_ENTER = 'enter'
EVENT_LEAVE = 'leave'
DEFAULT_EVENT = EVENT_ENTER

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'geo_location',
    vol.Required(CONF_SOURCE): cv.string,
    vol.Required(CONF_ZONE): entity_domain('zone'),
    vol.Required(CONF_EVENT, default=DEFAULT_EVENT):
        vol.Any(EVENT_ENTER, EVENT_LEAVE),
})


def source_match(state, source):
    """Check if the state matches the provided source."""
    return state and state.attributes.get('source') == source


async def async_trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    source = config.get(CONF_SOURCE).lower()
    zone_entity_id = config.get(CONF_ZONE)
    trigger_event = config.get(CONF_EVENT)

    @callback
    def state_change_listener(event):
        """Handle specific state changes."""
        # Skip if the event is not a geo_location entity.
        if not event.data.get('entity_id').startswith(DOMAIN):
            return
        # Skip if the event's source does not match the trigger's source.
        from_state = event.data.get('old_state')
        to_state = event.data.get('new_state')
        if not source_match(from_state, source) \
           and not source_match(to_state, source):
            return

        zone_state = hass.states.get(zone_entity_id)
        from_match = condition.zone(hass, zone_state, from_state)
        to_match = condition.zone(hass, zone_state, to_state)

        # pylint: disable=too-many-boolean-expressions
        if trigger_event == EVENT_ENTER and not from_match and to_match or \
           trigger_event == EVENT_LEAVE and from_match and not to_match:
            hass.async_run_job(action({
                'trigger': {
                    'platform': 'geo_location',
                    'source': source,
                    'entity_id': event.data.get('entity_id'),
                    'from_state': from_state,
                    'to_state': to_state,
                    'zone': zone_state,
                    'event': trigger_event,
                },
            }, context=event.context))

    return hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)
