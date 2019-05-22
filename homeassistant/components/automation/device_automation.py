"""Helpers for device automations."""
import importlib
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity_registry import async_entries_for_device

_LOGGER = logging.getLogger(__name__)


def _is_domain(entity, domain):
    return split_entity_id(entity.entity_id)[0] == domain


async def async_setup(hass):
    """Set up device automation."""
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_list_triggers)
    return True


async def async_get_device_automation_triggers(hass, device_id):
    """List device triggers."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    domains = set()
    triggers = []
    device = device_registry.async_get(device_id)
    for entry_id in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(entry_id)
        domains.add(config_entry.domain)

    entities = async_entries_for_device(entity_registry, device_id)
    for entity in entities:
        domains.add(split_entity_id(entity.entity_id)[0])

    for domain in domains:
        module = None
        try:
            module = importlib.import_module(
                '...{}.device_automation'.format(domain), __name__)
        except ImportError:
            _LOGGER.exception("Invalid domain %s", '...{}'.format(domain))
            continue

        if hasattr(module, 'DOMAIN_TRIGGERS'):
            pass
        if hasattr(module, 'ENTITY_TRIGGERS'):
            # Generate trigger for each matching entity
            domain_entities = [x for x in entities if _is_domain(x, domain)]
            for entity in domain_entities:
                for trigger in module.ENTITY_TRIGGERS:
                    trigger = dict(trigger)
                    trigger.update(entity_id=entity.entity_id)
                    triggers.append(trigger)

    return triggers


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'automation/device_automation/list_triggers',
    vol.Required('device_id'): str,
})
async def websocket_device_automation_list_triggers(hass, connection, msg):
    """Handle request for device triggers."""
    device_id = msg['device_id']
    triggers = await async_get_device_automation_triggers(hass, device_id)
    connection.send_result(msg['id'], {'triggers':triggers})
