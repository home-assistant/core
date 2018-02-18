"""Service calling related helpers."""
import asyncio
import logging
# pylint: disable=unused-import
from typing import Optional  # NOQA
from os import path

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.core as ha
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.loader import get_component, bind_hass
from homeassistant.util.yaml import load_yaml
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

CONF_SERVICE = 'service'
CONF_SERVICE_TEMPLATE = 'service_template'
CONF_SERVICE_ENTITY_ID = 'entity_id'
CONF_SERVICE_DATA = 'data'
CONF_SERVICE_DATA_TEMPLATE = 'data_template'

_LOGGER = logging.getLogger(__name__)

SERVICE_DESCRIPTION_CACHE = 'service_description_cache'


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
        try:
            template.attach(hass, config[CONF_SERVICE_DATA_TEMPLATE])
            service_data.update(template.render_complex(
                config[CONF_SERVICE_DATA_TEMPLATE], variables))
        except TemplateError as ex:
            _LOGGER.error('Error rendering data template: %s', ex)
            return

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


@asyncio.coroutine
@bind_hass
def async_get_all_descriptions(hass):
    """Return descriptions (i.e. user documentation) for all service calls."""
    if SERVICE_DESCRIPTION_CACHE not in hass.data:
        hass.data[SERVICE_DESCRIPTION_CACHE] = {}
    description_cache = hass.data[SERVICE_DESCRIPTION_CACHE]

    format_cache_key = '{}.{}'.format

    def domain_yaml_file(domain):
        """Return the services.yaml location for a domain."""
        if domain == ha.DOMAIN:
            import homeassistant.components as components
            component_path = path.dirname(components.__file__)
        else:
            component_path = path.dirname(get_component(domain).__file__)
        return path.join(component_path, 'services.yaml')

    def load_services_files(yaml_files):
        """Load and parse services.yaml files."""
        loaded = {}
        for yaml_file in yaml_files:
            try:
                loaded[yaml_file] = load_yaml(yaml_file)
            except FileNotFoundError:
                loaded[yaml_file] = {}

        return loaded

    services = hass.services.async_services()

    # Load missing files
    missing = set()
    for domain in services:
        for service in services[domain]:
            if format_cache_key(domain, service) not in description_cache:
                missing.add(domain_yaml_file(domain))
                break

    if missing:
        loaded = yield from hass.async_add_job(load_services_files, missing)

    # Build response
    catch_all_yaml_file = domain_yaml_file(ha.DOMAIN)
    descriptions = {}
    for domain in services:
        descriptions[domain] = {}
        yaml_file = domain_yaml_file(domain)

        for service in services[domain]:
            cache_key = format_cache_key(domain, service)
            description = description_cache.get(cache_key)

            # Cache missing descriptions
            if description is None:
                if yaml_file == catch_all_yaml_file:
                    yaml_services = loaded[yaml_file].get(domain, {})
                else:
                    yaml_services = loaded[yaml_file]
                yaml_description = yaml_services.get(service, {})

                description = description_cache[cache_key] = {
                    'description': yaml_description.get('description', ''),
                    'fields': yaml_description.get('fields', {})
                }

            descriptions[domain][service] = description

    return descriptions
