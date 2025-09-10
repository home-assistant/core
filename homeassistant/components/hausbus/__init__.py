"""Integration for all haus-bus.de modules."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .gateway import HausbusGateway

# , Platform.NUMBER
PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.EVENT,
    Platform.COVER,
    Platform.BUTTON,
    Platform.NUMBER,
]

LOGGER = logging.getLogger(__name__)


@dataclass
class HausbusConfig:
    """Class for Hausbus ConfigEntry."""

    gateway: HausbusGateway


HausbusConfigEntry: TypeAlias = ConfigEntry[HausbusConfig]


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entity_info"] = {}

    gateway = HausbusGateway(hass, entry)
    entry.runtime_data = HausbusConfig(gateway)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Creates a button to manually start device discovery
    hass.async_create_task(gateway.createDiscoveryButtonAndStartDiscovery())

    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Haus-Bus integration (global services etc.)."""

    async def discover_devices(call: ServiceCall):
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("No Hausbus-Gateway available")

        LOGGER.debug("Search devices service called")
        gateway = entries[0].runtime_data.gateway
        gateway.home_server.searchDevices()

    hass.services.async_register(DOMAIN, "discover_devices", discover_devices)

    async def reset_service(call):
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("No Hausbus-Gateway available")

        device_id = call.data.get("device_id")
        if not device_id or not isinstance(device_id, str):
            raise HomeAssistantError("device_id missing")

        LOGGER.debug("Reset device %s called", device_id)
        gateway = entries[0].runtime_data.gateway
        try:
            gateway.resetDevice(device_id)
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to reset device {device_id}: {err}"
            ) from err

    hass.services.async_register(DOMAIN, "reset_device", reset_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data.gateway

    gateway.home_server.removeBusEventListener(gateway)
    hass.services.async_remove(DOMAIN, "discover_devices")
    hass.services.async_remove(DOMAIN, "reset_device")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(hass, config_entry, device_entry):
    """Handle removal of a device from the integration."""

    gateway = config_entry.runtime_data.gateway

    identifiers = device_entry.identifiers
    for domain, device_id in identifiers:
        if domain == DOMAIN:
            return bool(await gateway.removeDevice(device_id))

    return False
