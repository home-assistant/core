"""
homeassistant.components.automation.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers state listening automation rules.
"""
import logging

from homeassistant.helpers.event import track_state_change
from homeassistant.const import MATCH_ALL


CONF_ENTITY_ID = "entity_id"
CONF_FROM = "from"
CONF_TO = "to"
CONF_STATE = "state"


def trigger(hass, config, action):
    """ Listen for state changes based on `config`. """
    entity_id = config.get(CONF_ENTITY_ID)

    if entity_id is None:
        logging.getLogger(__name__).error(
            "Missing trigger configuration key %s", CONF_ENTITY_ID)
        return False

    from_state = config.get(CONF_FROM, MATCH_ALL)
    to_state = config.get(CONF_TO) or config.get(CONF_STATE) or MATCH_ALL

    def state_automation_listener(entity, from_s, to_s):
        """ Listens for state changes and calls action. """
        action()

    track_state_change(
        hass, entity_id, state_automation_listener, from_state, to_state)

    return True


def if_action(hass, config):
    """ Wraps action method with state based condition. """
    entity_id = config.get(CONF_ENTITY_ID)
    state = config.get(CONF_STATE)

    if entity_id is None or state is None:
        logging.getLogger(__name__).error(
            "Missing if-condition configuration key %s or %s", CONF_ENTITY_ID,
            CONF_STATE)
        return None

    state = str(state)

    def if_state():
        """ Test if condition. """
        return hass.states.is_state(entity_id, state)

    return if_state
