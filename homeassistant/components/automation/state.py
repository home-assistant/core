"""
homeassistant.components.automation.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers state listening automation rules.
"""
import logging

from homeassistant.const import MATCH_ALL


CONF_ENTITY_ID = "state_entity_id"
CONF_FROM = "state_from"
CONF_TO = "state_to"


def register(hass, config, action):
    """ Listen for state changes based on `config`. """
    entity_id = config.get(CONF_ENTITY_ID)

    if entity_id is None:
        logging.getLogger(__name__).error(
            "Missing configuration key %s", CONF_ENTITY_ID)
        return False

    from_state = config.get(CONF_FROM, MATCH_ALL)
    to_state = config.get(CONF_TO, MATCH_ALL)

    def state_automation_listener(entity, from_s, to_s):
        """ Listens for state changes and calls action. """
        action()

    hass.states.track_change(
        entity_id, state_automation_listener, from_state, to_state)

    return True
