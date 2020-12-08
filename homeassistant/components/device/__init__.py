"""Helpers for device."""
import asyncio
from functools import wraps
import logging
from types import ModuleType
from typing import Any, MutableMapping

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.loader import IntegrationNotFound
from homeassistant.requirements import async_get_integration_with_requirements

from .exceptions import DeviceNotFound, InvalidDevice

# mypy: allow-untyped-calls, allow-untyped-defs

DOMAIN = "device"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up device."""
    hass.components.websocket_api.async_register_command(
        websocket_device_get_device_info
    )
    return True


async def async_get_device_platform(hass: HomeAssistant, domain: str) -> ModuleType:
    """Load device platform for integration.

    Throws InvalidDeviceConfig if the integration is not found or does not support device info.
    """
    try:
        integration = await async_get_integration_with_requirements(hass, domain)
        platform = integration.get_platform("device")
    except IntegrationNotFound as err:
        raise InvalidDevice(f"Integration '{domain}' not found") from err
    except ImportError as err:
        raise InvalidDevice(
            f"Integration '{domain}' does not support device info"
        ) from err

    return platform


async def _async_get_device_info_from_domain(hass, domain, device_id, entry_id):
    """Get device info."""
    try:
        platform = await async_get_device_platform(hass, domain)
    except InvalidDevice:
        return None

    if not hasattr(platform, "async_get_device_info"):
        return None

    return (entry_id, await getattr(platform, "async_get_device_info")(hass, device_id))


async def _async_get_device_info(hass, device_id):
    """List device info."""
    device_registry = await hass.helpers.device_registry.async_get_registry()

    domains = set()
    infos: MutableMapping[str, Any] = {}
    device = device_registry.async_get(device_id)

    if device is None:
        raise DeviceNotFound

    for entry_id in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(entry_id)
        domains.add((config_entry.domain, entry_id))

    device_infos = await asyncio.gather(
        *(
            _async_get_device_info_from_domain(hass, domain, device_id, entry_id)
            for domain, entry_id in domains
        )
    )
    for device_info in device_infos:
        if device_info is not None:
            infos[device_info[0]] = device_info[1]

    return infos


def handle_device_errors(func):
    """Handle device API errors."""

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
        vol.Required("type"): "device/info",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
@handle_device_errors
async def websocket_device_get_device_info(hass, connection, msg):
    """Handle request for device actions."""
    device_id = msg["device_id"]
    info = await _async_get_device_info(hass, device_id)
    connection.send_result(msg["id"], info)
