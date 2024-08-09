"""The Haus-Bus integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_entry import HausbusConfig, HausbusConfigEntry
from .const import DOMAIN
from .gateway import HausbusGateway

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    gateway = HausbusGateway(hass, entry)
    entry.runtime_data = HausbusConfig(gateway)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("start searching devices")

    # search devices after adding all callbacks to the gateway object
    hass.async_add_executor_job(gateway.home_server.searchDevices)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data.gateway
    gateway.home_server.removeBusEventListener(gateway)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
