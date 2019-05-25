"""Helpers for device automations."""
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.loader import async_get_integration, IntegrationNotFound

DOMAIN = 'device_automation'

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
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
        integration = None
        try:
            integration = await async_get_integration(hass, domain)
        except IntegrationNotFound:
            _LOGGER.exception('Integration %s not found', domain)
            continue

        try:
            platform = integration.get_platform('device_automation')
        except ImportError:
            # The domain does not have device automations, continue
            continue

        if hasattr(platform, 'async_get_triggers'):
            triggers.extend(await platform.async_get_triggers(hass, device_id))

    return triggers


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'device_automation/list_triggers',
    vol.Required('device_id'): str,
})
async def websocket_device_automation_list_triggers(hass, connection, msg):
    """Handle request for device triggers."""
    device_id = msg['device_id']
    triggers = await async_get_device_automation_triggers(hass, device_id)
    connection.send_result(msg['id'], {'triggers': triggers})
