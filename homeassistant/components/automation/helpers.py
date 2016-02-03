"""
homeassistant.components.automation.helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Offers helper functions for automation rules.

"""
import logging

from homeassistant.helpers import service

CONF_ENTITY_ID = "entity_id"
CONF_EXPAND_IDS = "expand_ids"

_LOGGER = logging.getLogger(__name__)


def get_entity_ids(hass, config):
    """ Get entity ids from the conf and expand if wanted. """
    entity_id = config.get(CONF_ENTITY_ID)
    expand = config.get(CONF_EXPAND_IDS, None)

    if entity_id is None:
        _LOGGER.error("Missing configuration key %s", CONF_ENTITY_ID)
        return None

    if expand:
        entity_id_old = entity_id
        entity_id = service.expand_entity_ids(hass, entity_id=entity_id)
        _LOGGER.debug("Expanded entity_ids %s to %s", entity_id_old,
                      entity_id)

    return entity_id
