"""Helpers for device automations."""
import asyncio
import logging
from typing import Any, List, MutableMapping

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, CONF_DOMAIN, CONF_DEVICE_ID
from homeassistant.components import websocket_api
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.loader import async_get_integration, IntegrationNotFound

from .exceptions import InvalidDeviceAutomationConfig


# mypy: allow-untyped-calls, allow-untyped-defs

DOMAIN = "device_automation"

_LOGGER = logging.getLogger(__name__)


TRIGGER_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_DEVICE_ID): str,
    }
)

TYPES = {
    "trigger": ("device_trigger", "async_get_triggers"),
    "condition": ("device_condition", "async_get_conditions"),
    "action": ("device_action", "async_get_actions"),
}


async def async_setup(hass, config):
    """Set up device automation."""
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_list_actions
    )
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_list_conditions
    )
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_list_triggers
    )
    return True


async def async_get_device_automation_platform(hass, config, automation_type):
    """Load device automation platform for integration.

    Throws InvalidDeviceAutomationConfig if the integration is not found or does not support device automation.
    """
    platform_name, _ = TYPES[automation_type]
    try:
        integration = await async_get_integration(hass, config[CONF_DOMAIN])
        platform = integration.get_platform(platform_name)
    except IntegrationNotFound:
        raise InvalidDeviceAutomationConfig(
            f"Integration '{config[CONF_DOMAIN]}' not found"
        )
    except ImportError:
        raise InvalidDeviceAutomationConfig(
            f"Integration '{config[CONF_DOMAIN]}' does not support device automation {automation_type}s"
        )

    return platform


async def _async_get_device_automations_from_domain(
    hass, domain, automation_type, device_id
):
    """List device automations."""
    integration = None
    try:
        integration = await async_get_integration(hass, domain)
    except IntegrationNotFound:
        _LOGGER.warning("Integration %s not found", domain)
        return None

    platform_name, function_name = TYPES[automation_type]

    try:
        platform = integration.get_platform(platform_name)
    except ImportError:
        # The domain does not have device automations
        return None

    return await getattr(platform, function_name)(hass, device_id)


async def _async_get_device_automations(hass, automation_type, device_id):
    """List device automations."""
    device_registry, entity_registry = await asyncio.gather(
        hass.helpers.device_registry.async_get_registry(),
        hass.helpers.entity_registry.async_get_registry(),
    )

    domains = set()
    automations: List[MutableMapping[str, Any]] = []
    device = device_registry.async_get(device_id)
    for entry_id in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(entry_id)
        domains.add(config_entry.domain)

    entity_entries = async_entries_for_device(entity_registry, device_id)
    for entity_entry in entity_entries:
        domains.add(entity_entry.domain)

    device_automations = await asyncio.gather(
        *(
            _async_get_device_automations_from_domain(
                hass, domain, automation_type, device_id
            )
            for domain in domains
        )
    )
    for device_automation in device_automations:
        if device_automation is not None:
            automations.extend(device_automation)

    return automations


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/action/list",
        vol.Required("device_id"): str,
    }
)
async def websocket_device_automation_list_actions(hass, connection, msg):
    """Handle request for device actions."""
    device_id = msg["device_id"]
    actions = await _async_get_device_automations(hass, "action", device_id)
    connection.send_result(msg["id"], actions)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/condition/list",
        vol.Required("device_id"): str,
    }
)
async def websocket_device_automation_list_conditions(hass, connection, msg):
    """Handle request for device conditions."""
    device_id = msg["device_id"]
    conditions = await _async_get_device_automations(hass, "condition", device_id)
    connection.send_result(msg["id"], conditions)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/trigger/list",
        vol.Required("device_id"): str,
    }
)
async def websocket_device_automation_list_triggers(hass, connection, msg):
    """Handle request for device triggers."""
    device_id = msg["device_id"]
    triggers = await _async_get_device_automations(hass, "trigger", device_id)
    connection.send_result(msg["id"], triggers)
