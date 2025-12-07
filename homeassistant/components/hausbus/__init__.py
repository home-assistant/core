"""Integration for all haus-bus.de modules."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .gateway import HausbusGateway

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

    # start device discovery
    hass.async_create_task(gateway.start_discovery())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""

    gateway = entry.runtime_data
    gateway.home_server.removeBusEventListener(gateway)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
