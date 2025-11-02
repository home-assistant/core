"""Integration for all haus-bus.de modules."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .gateway import HausbusGateway

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.COVER,
]

LOGGER = logging.getLogger(__name__)


type HausbusConfigEntry = ConfigEntry[HausbusGateway]


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus integration from a config entry."""

    gateway = HausbusGateway(hass, entry)
    entry.runtime_data = gateway

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Creates a button to manually start device discovery
    hass.async_create_task(gateway.create_discovery_button())
    return True


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Haus-Bus integration (global services etc.)."""

    async def discover_devices(call: ServiceCall):
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("No Hausbus-Gateway available")

        LOGGER.debug("Search devices service called")
        gateway = entries[0].runtime_data
        gateway.home_server.searchDevices()

    hass.services.async_register(DOMAIN, "discover_devices", discover_devices)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data

    gateway.home_server.removeBusEventListener(gateway)
    hass.services.async_remove(DOMAIN, "discover_devices")
    hass.services.async_remove(DOMAIN, "reset_device")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
