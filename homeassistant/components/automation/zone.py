"""
Offer zone automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#zone-trigger
"""
import logging

from homeassistant.components import zone
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE, MATCH_ALL)
from homeassistant.helpers.event import track_state_change

CONF_ENTITY_ID = "entity_id"
CONF_ZONE = "zone"
CONF_EVENT = "event"
EVENT_ENTER = "enter"
EVENT_LEAVE = "leave"
DEFAULT_EVENT = EVENT_ENTER


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)

    if entity_id is None or zone_entity_id is None:
        logging.getLogger(__name__).error(
            "Missing trigger configuration key %s or %s", CONF_ENTITY_ID,
            CONF_ZONE)
        return False

    event = config.get(CONF_EVENT, DEFAULT_EVENT)

    def zone_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        if from_s and None in (from_s.attributes.get(ATTR_LATITUDE),
                               from_s.attributes.get(ATTR_LONGITUDE)) or \
            None in (to_s.attributes.get(ATTR_LATITUDE),
                     to_s.attributes.get(ATTR_LONGITUDE)):
            return

        from_match = _in_zone(hass, zone_entity_id, from_s) if from_s else None
        to_match = _in_zone(hass, zone_entity_id, to_s)

        # pylint: disable=too-many-boolean-expressions
        if event == EVENT_ENTER and not from_match and to_match or \
           event == EVENT_LEAVE and from_match and not to_match:
            action()

    track_state_change(
        hass, entity_id, zone_automation_listener, MATCH_ALL, MATCH_ALL)

    return True


def if_action(hass, config):
    """Wrap action method with zone based condition."""
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)

    if entity_id is None or zone_entity_id is None:
        logging.getLogger(__name__).error(
            "Missing condition configuration key %s or %s", CONF_ENTITY_ID,
            CONF_ZONE)
        return False

    def if_in_zone():
        """Test if condition."""
        return _in_zone(hass, zone_entity_id, hass.states.get(entity_id))

    return if_in_zone


def _in_zone(hass, zone_entity_id, state):
    """Check if state is in zone."""
    if not state or None in (state.attributes.get(ATTR_LATITUDE),
                             state.attributes.get(ATTR_LONGITUDE)):
        return False

    zone_state = hass.states.get(zone_entity_id)
    return zone_state and zone.in_zone(
        zone_state, state.attributes.get(ATTR_LATITUDE),
        state.attributes.get(ATTR_LONGITUDE),
        state.attributes.get(ATTR_GPS_ACCURACY, 0))
