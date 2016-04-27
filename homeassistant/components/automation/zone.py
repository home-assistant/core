"""
Offer zone automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#zone-trigger
"""
import voluptuous as vol

from homeassistant.components import zone
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE, MATCH_ALL, CONF_PLATFORM)
from homeassistant.helpers.event import track_state_change
import homeassistant.helpers.config_validation as cv

CONF_ENTITY_ID = "entity_id"
CONF_ZONE = "zone"
CONF_EVENT = "event"
EVENT_ENTER = "enter"
EVENT_LEAVE = "leave"
DEFAULT_EVENT = EVENT_ENTER

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'zone',
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_ZONE): cv.entity_id,
    vol.Required(CONF_EVENT, default=DEFAULT_EVENT):
        vol.Any(EVENT_ENTER, EVENT_LEAVE),
})

IF_ACTION_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'zone',
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_ZONE): cv.entity_id,
})


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)
    event = config.get(CONF_EVENT)

    def zone_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        if from_s and None in (from_s.attributes.get(ATTR_LATITUDE),
                               from_s.attributes.get(ATTR_LONGITUDE)) or \
            None in (to_s.attributes.get(ATTR_LATITUDE),
                     to_s.attributes.get(ATTR_LONGITUDE)):
            return

        zone_state = hass.states.get(zone_entity_id)
        from_match = _in_zone(hass, zone_state, from_s) if from_s else None
        to_match = _in_zone(hass, zone_state, to_s)

        # pylint: disable=too-many-boolean-expressions
        if event == EVENT_ENTER and not from_match and to_match or \
           event == EVENT_LEAVE and from_match and not to_match:
            action({
                'trigger': {
                    'platform': 'zone',
                    'entity_id': entity,
                    'from_state': from_s,
                    'to_state': to_s,
                    'zone': zone_state,
                },
            })

    track_state_change(
        hass, entity_id, zone_automation_listener, MATCH_ALL, MATCH_ALL)

    return True


def if_action(hass, config):
    """Wrap action method with zone based condition."""
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)

    def if_in_zone(variables):
        """Test if condition."""
        zone_state = hass.states.get(zone_entity_id)
        return _in_zone(hass, zone_state, hass.states.get(entity_id))

    return if_in_zone


def _in_zone(hass, zone_state, state):
    """Check if state is in zone."""
    if not state or None in (state.attributes.get(ATTR_LATITUDE),
                             state.attributes.get(ATTR_LONGITUDE)):
        return False

    return zone_state and zone.in_zone(
        zone_state, state.attributes.get(ATTR_LATITUDE),
        state.attributes.get(ATTR_LONGITUDE),
        state.attributes.get(ATTR_GPS_ACCURACY, 0))
