"""Helpers for device automations."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from functools import wraps
import logging
from types import ModuleType
from typing import Any, NamedTuple

import voluptuous as vol
import voluptuous_serialize

from homeassistant.components import websocket_api
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.loader import IntegrationNotFound, bind_hass
from homeassistant.requirements import async_get_integration_with_requirements

from .exceptions import DeviceNotFound, InvalidDeviceAutomationConfig

# mypy: allow-untyped-calls, allow-untyped-defs

DOMAIN = "device_automation"

DEVICE_TRIGGER_BASE_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_DEVICE_ID): str,
    }
)


class DeviceAutomationDetails(NamedTuple):
    """Details for device automation."""

    section: str
    get_automations_func: str
    get_capabilities_func: str


TYPES = {
    "trigger": DeviceAutomationDetails(
        "device_trigger",
        "async_get_triggers",
        "async_get_trigger_capabilities",
    ),
    "condition": DeviceAutomationDetails(
        "device_condition",
        "async_get_conditions",
        "async_get_condition_capabilities",
    ),
    "action": DeviceAutomationDetails(
        "device_action",
        "async_get_actions",
        "async_get_action_capabilities",
    ),
}


@bind_hass
async def async_get_device_automations(
    hass: HomeAssistant,
    automation_type: str,
    device_ids: Iterable[str] | None = None,
) -> Mapping[str, Any]:
    """Return all the device automations for a type optionally limited to specific device ids."""
    return await _async_get_device_automations(hass, automation_type, device_ids)


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
    platform_name = TYPES[automation_type].section
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
    hass, domain, automation_type, device_ids, return_exceptions
):
    """List device automations."""
    try:
        platform = await async_get_device_automation_platform(
            hass, domain, automation_type
        )
    except InvalidDeviceAutomationConfig:
        return {}

    function_name = TYPES[automation_type].get_automations_func

    return await asyncio.gather(
        *(
            getattr(platform, function_name)(hass, device_id)
            for device_id in device_ids
        ),
        return_exceptions=return_exceptions,
    )


async def _async_get_device_automations(
    hass: HomeAssistant, automation_type: str, device_ids: Iterable[str] | None
) -> Mapping[str, list[dict[str, Any]]]:
    """List device automations."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    domain_devices: dict[str, set[str]] = {}
    device_entities_domains: dict[str, set[str]] = {}
    match_device_ids = set(device_ids or device_registry.devices)
    combined_results: dict[str, list[dict[str, Any]]] = {}

    for entry in entity_registry.entities.values():
        if not entry.disabled_by and entry.device_id in match_device_ids:
            device_entities_domains.setdefault(entry.device_id, set()).add(entry.domain)

    for device_id in match_device_ids:
        combined_results[device_id] = []
        device = device_registry.async_get(device_id)
        if device is None:
            raise DeviceNotFound
        for entry_id in device.config_entries:
            if config_entry := hass.config_entries.async_get_entry(entry_id):
                domain_devices.setdefault(config_entry.domain, set()).add(device_id)
        for domain in device_entities_domains.get(device_id, []):
            domain_devices.setdefault(domain, set()).add(device_id)

    # If specific device ids were requested, we allow
    # InvalidDeviceAutomationConfig to be thrown, otherwise we skip
    # devices that do not have valid triggers
    return_exceptions = not bool(device_ids)

    for domain_results in await asyncio.gather(
        *(
            _async_get_device_automations_from_domain(
                hass, domain, automation_type, domain_device_ids, return_exceptions
            )
            for domain, domain_device_ids in domain_devices.items()
        )
    ):
        for device_results in domain_results:
            if device_results is None or isinstance(
                device_results, InvalidDeviceAutomationConfig
            ):
                continue
            if isinstance(device_results, Exception):
                logging.getLogger(__name__).error(
                    "Unexpected error fetching device %ss",
                    automation_type,
                    exc_info=device_results,
                )
                continue
            for automation in device_results:
                combined_results[automation["device_id"]].append(automation)

    return combined_results


async def _async_get_device_automation_capabilities(hass, automation_type, automation):
    """List device automations."""
    try:
        platform = await async_get_device_automation_platform(
            hass, automation[CONF_DOMAIN], automation_type
        )
    except InvalidDeviceAutomationConfig:
        return {}

    function_name = TYPES[automation_type].get_capabilities_func

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
    actions = (await _async_get_device_automations(hass, "action", [device_id])).get(
        device_id
    )
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
    conditions = (
        await _async_get_device_automations(hass, "condition", [device_id])
    ).get(device_id)
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
    triggers = (await _async_get_device_automations(hass, "trigger", [device_id])).get(
        device_id
    )
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
