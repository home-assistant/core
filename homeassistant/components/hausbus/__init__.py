"""The Haus-Bus integration."""
from __future__ import annotations

import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .gateway import HausbusGateway

# Only support light platform on the initial version. Additional platforms to follow
PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Haus-Bus from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    gateway = HausbusGateway(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = gateway

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("start searching devices")

    # search devices after adding all callbacks to the gateway object
    gateway.home_server.searchDevices()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = cast(HausbusGateway, hass.data[DOMAIN][entry.entry_id])
    gateway.home_server.removeBusEventListener(gateway)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
