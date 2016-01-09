"""Service calling related helpers."""
import logging

from homeassistant.util import split_entity_id
from homeassistant.const import ATTR_ENTITY_ID

CONF_SERVICE = 'service'
CONF_SERVICE_ENTITY_ID = 'entity_id'
CONF_SERVICE_DATA = 'data'

_LOGGER = logging.getLogger(__name__)


def call_from_config(hass, config, blocking=False):
    """Call a service based on a config hash."""
    if CONF_SERVICE not in config:
        _LOGGER.error('Missing key %s: %s', CONF_SERVICE, config)
        return

    domain, service = split_entity_id(config[CONF_SERVICE])
    service_data = config.get(CONF_SERVICE_DATA)

    if service_data is None:
        service_data = {}
    elif isinstance(service_data, dict):
        service_data = dict(service_data)
    else:
        _LOGGER.error("%s should be a dictionary", CONF_SERVICE_DATA)
        service_data = {}

    entity_id = config.get(CONF_SERVICE_ENTITY_ID)
    if isinstance(entity_id, str):
        service_data[ATTR_ENTITY_ID] = [ent.strip() for ent in
                                        entity_id.split(",")]
    elif entity_id is not None:
        service_data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(domain, service, service_data, blocking)
