"""Service calling related helpers."""
import asyncio
import logging
# pylint: disable=unused-import
from typing import Optional  # NOQA

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant  # NOQA
from homeassistant.exceptions import TemplateError
from homeassistant.loader import get_component, bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

CONF_SERVICE = 'service'
CONF_SERVICE_TEMPLATE = 'service_template'
CONF_SERVICE_ENTITY_ID = 'entity_id'
CONF_SERVICE_DATA = 'data'
CONF_SERVICE_DATA_TEMPLATE = 'data_template'

_LOGGER = logging.getLogger(__name__)


@bind_hass
def call_from_config(hass, config, blocking=False, variables=None,
                     validate_config=True):
    """Call a service based on a config hash."""
    run_coroutine_threadsafe(
        async_call_from_config(hass, config, blocking, variables,
                               validate_config), hass.loop).result()


@asyncio.coroutine
@bind_hass
def async_call_from_config(hass, config, blocking=False, variables=None,
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
            config[CONF_SERVICE_TEMPLATE].hass = hass
            domain_service = config[CONF_SERVICE_TEMPLATE].async_render(
                variables)
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
        def _data_template_creator(value):
            """Recursive template creator helper function."""
            if isinstance(value, list):
                return [_data_template_creator(item) for item in value]
            elif isinstance(value, dict):
                return {key: _data_template_creator(item)
                        for key, item in value.items()}
            value.hass = hass
            return value.async_render(variables)
        service_data.update(_data_template_creator(
            config[CONF_SERVICE_DATA_TEMPLATE]))

    if CONF_SERVICE_ENTITY_ID in config:
        service_data[ATTR_ENTITY_ID] = config[CONF_SERVICE_ENTITY_ID]

    yield from hass.services.async_call(
        domain, service_name, service_data, blocking)


@bind_hass
def extract_entity_ids(hass, service_call, expand_group=True):
    """Extract a list of entity ids from a service call.

    Will convert group entity ids to the entity ids it represents.

    Async friendly.
    """
    if not (service_call.data and ATTR_ENTITY_ID in service_call.data):
        return []

    group = get_component('group')

    # Entity ID attr can be a list or a string
    service_ent_id = service_call.data[ATTR_ENTITY_ID]

    if expand_group:

        if isinstance(service_ent_id, str):
            return group.expand_entity_ids(hass, [service_ent_id])

        return [ent_id for ent_id in
                group.expand_entity_ids(hass, service_ent_id)]

    else:

        if isinstance(service_ent_id, str):
            return [service_ent_id]

        return service_ent_id
