"""Integration for all haus-bus.de modules."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .gateway import HausbusGateway

PLATFORMS: list[Platform] = [
    Platform.COVER,
]

LOGGER = logging.getLogger(__name__)


type HausbusConfigEntry = ConfigEntry[HausbusGateway]


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus integration from a config entry."""
    try:
        gateway = await HausbusGateway.async_create(hass, entry)
    except OSError as err:
        raise ConfigEntryNotReady(
            "Unable to open the Haus-Bus network connection"
        ) from err

    entry.runtime_data = gateway

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        gateway.home_server.removeBusEventListener(gateway)
        gateway.home_server.removeBusDeviceListener(gateway)
        raise

    # start device discovery
    hass.async_create_task(gateway.start_discovery())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data
    gateway.home_server.removeBusEventListener(gateway)
    gateway.home_server.removeBusDeviceListener(gateway)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
