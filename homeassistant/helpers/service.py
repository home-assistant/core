"""Service calling related helpers."""
import functools
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv

HASS = None

CONF_SERVICE = 'service'
CONF_SERVICE_TEMPLATE = 'service_template'
CONF_SERVICE_ENTITY_ID = 'entity_id'
CONF_SERVICE_DATA = 'data'
CONF_SERVICE_DATA_TEMPLATE = 'data_template'

_LOGGER = logging.getLogger(__name__)


def service(domain, service_name):
    """Decorator factory to register a service."""
    def register_service_decorator(action):
        """Decorator to register a service."""
        HASS.services.register(domain, service_name,
                               functools.partial(action, HASS))
        return action

    return register_service_decorator


def call_from_config(hass, config, blocking=False, variables=None,
                     validate_config=True):
    """Call a service based on a config hash."""
    if validate_config:
        try:
            config = cv.SERVICE_SCHEMA(config)
        except vol.Invalid as ex:
            _LOGGER.error("Invalid config for calling service: %s", ex)
            return

    if CONF_SERVICE in config:
        domain_service = config[CONF_SERVICE]
    else:
        try:
            domain_service = template.render(
                hass, config[CONF_SERVICE_TEMPLATE], variables)
            domain_service = cv.service(domain_service)
        except TemplateError as ex:
            _LOGGER.error('Error rendering service name template: %s', ex)
            return
        except vol.Invalid as ex:
            _LOGGER.error('Template rendered invalid service: %s',
                          domain_service)
            return

    domain, service_name = domain_service.split('.', 1)
    service_data = dict(config.get(CONF_SERVICE_DATA, {}))

    if CONF_SERVICE_DATA_TEMPLATE in config:
        for key, value in config[CONF_SERVICE_DATA_TEMPLATE].items():
            service_data[key] = template.render(hass, value, variables)

    if CONF_SERVICE_ENTITY_ID in config:
        service_data[ATTR_ENTITY_ID] = config[CONF_SERVICE_ENTITY_ID]

    hass.services.call(domain, service_name, service_data, blocking)


def extract_entity_ids(hass, service_call):
    """Helper method to extract a list of entity ids from a service call.

    Will convert group entity ids to the entity ids it represents.
    """
    if not (service_call.data and ATTR_ENTITY_ID in service_call.data):
        return []

    group = get_component('group')

    # Entity ID attr can be a list or a string
    service_ent_id = service_call.data[ATTR_ENTITY_ID]

    if isinstance(service_ent_id, str):
        return group.expand_entity_ids(hass, [service_ent_id])

    return [ent_id for ent_id in group.expand_entity_ids(hass, service_ent_id)]
