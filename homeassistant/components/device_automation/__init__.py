"""Helpers for device automations."""
import asyncio
from functools import wraps
from types import ModuleType
from typing import Any, List, MutableMapping

import voluptuous as vol
import voluptuous_serialize

from homeassistant.components import websocket_api
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.loader import IntegrationNotFound
from homeassistant.requirements import async_get_integration_with_requirements

from .exceptions import DeviceNotFound, InvalidDeviceAutomationConfig

# mypy: allow-untyped-calls, allow-untyped-defs

DOMAIN = "device_automation"


TRIGGER_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_DEVICE_ID): str,
    }
)

TYPES = {
    # platform name, get automations function, get capabilities function
    "trigger": (
        "device_trigger",
        "async_get_triggers",
        "async_get_trigger_capabilities",
    ),
    "condition": (
        "device_condition",
        "async_get_conditions",
        "async_get_condition_capabilities",
    ),
    "action": ("device_action", "async_get_actions", "async_get_action_capabilities"),
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
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_get_action_capabilities
    )
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_get_condition_capabilities
    )
    hass.components.websocket_api.async_register_command(
        websocket_device_automation_get_trigger_capabilities
    )
    return True


async def async_get_device_automation_platform(
    hass: HomeAssistant, domain: str, automation_type: str
) -> ModuleType:
    """Load device automation platform for integration.

    Throws InvalidDeviceAutomationConfig if the integration is not found or does not support device automation.
    """
    platform_name = TYPES[automation_type][0]
    try:
        integration = await async_get_integration_with_requirements(hass, domain)
        platform = integration.get_platform(platform_name)
    except IntegrationNotFound as err:
        raise InvalidDeviceAutomationConfig(
            f"Integration '{domain}' not found"
        ) from err
    except ImportError as err:
        raise InvalidDeviceAutomationConfig(
            f"Integration '{domain}' does not support device automation {automation_type}s"
        ) from err

    return platform


async def _async_get_device_automations_from_domain(
    hass, domain, automation_type, device_id
):
    """List device automations."""
    try:
        platform = await async_get_device_automation_platform(
            hass, domain, automation_type
        )
    except InvalidDeviceAutomationConfig:
        return None

    function_name = TYPES[automation_type][1]

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

    if device is None:
        raise DeviceNotFound

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


async def _async_get_device_automation_capabilities(hass, automation_type, automation):
    """List device automations."""
    try:
        platform = await async_get_device_automation_platform(
            hass, automation[CONF_DOMAIN], automation_type
        )
    except InvalidDeviceAutomationConfig:
        return {}

    function_name = TYPES[automation_type][2]

    if not hasattr(platform, function_name):
        # The device automation has no capabilities
        return {}

    try:
        capabilities = await getattr(platform, function_name)(hass, automation)
    except InvalidDeviceAutomationConfig:
        return {}

    capabilities = capabilities.copy()

    extra_fields = capabilities.get("extra_fields")
    if extra_fields is None:
        capabilities["extra_fields"] = []
    else:
        capabilities["extra_fields"] = voluptuous_serialize.convert(
            extra_fields, custom_serializer=cv.custom_serializer
        )

    return capabilities


def handle_device_errors(func):
    """Handle device automation errors."""

    @wraps(func)
    async def with_error_handling(hass, connection, msg):
        try:
            await func(hass, connection, msg)
        except DeviceNotFound:
            connection.send_error(
                msg["id"], websocket_api.const.ERR_NOT_FOUND, "Device not found"
            )

    return with_error_handling


@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/action/list",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_automation_list_actions(hass, connection, msg):
    """Handle request for device actions."""
    device_id = msg["device_id"]
    actions = await _async_get_device_automations(hass, "action", device_id)
    connection.send_result(msg["id"], actions)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/condition/list",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_automation_list_conditions(hass, connection, msg):
    """Handle request for device conditions."""
    device_id = msg["device_id"]
    conditions = await _async_get_device_automations(hass, "condition", device_id)
    connection.send_result(msg["id"], conditions)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/trigger/list",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_automation_list_triggers(hass, connection, msg):
    """Handle request for device triggers."""
    device_id = msg["device_id"]
    triggers = await _async_get_device_automations(hass, "trigger", device_id)
    connection.send_result(msg["id"], triggers)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/action/capabilities",
        vol.Required("action"): dict,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_automation_get_action_capabilities(hass, connection, msg):
    """Handle request for device action capabilities."""
    action = msg["action"]
    capabilities = await _async_get_device_automation_capabilities(
        hass, "action", action
    )
    connection.send_result(msg["id"], capabilities)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/condition/capabilities",
        vol.Required("condition"): dict,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_automation_get_condition_capabilities(hass, connection, msg):
    """Handle request for device condition capabilities."""
    condition = msg["condition"]
    capabilities = await _async_get_device_automation_capabilities(
        hass, "condition", condition
    )
    connection.send_result(msg["id"], capabilities)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "device_automation/trigger/capabilities",
        vol.Required("trigger"): dict,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_automation_get_trigger_capabilities(hass, connection, msg):
    """Handle request for device trigger capabilities."""
    trigger = msg["trigger"]
    capabilities = await _async_get_device_automation_capabilities(
        hass, "trigger", trigger
    )
    connection.send_result(msg["id"], capabilities)
