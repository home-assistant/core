"""The Sensoterra integration."""

from __future__ import annotations

import logging

from sensoterra.customerapi import CustomerApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION
from .coordinator import SensoterraCoordinator

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensoterra from a config entry."""

    # if hass.data.get(DOMAIN) is None:
    #     hass.data.setdefault(DOMAIN, {})
    #     _LOGGER.info(STARTUP_MESSAGE)

    _LOGGER.info("Initializing version %s", VERSION)

    hass.data.setdefault(DOMAIN, {})

    api = CustomerApi()
    api.set_language(hass.config.language)
    _LOGGER.debug("Version %s", api.get_version())

    api.set_token(entry.data["token"])

    coordinator = SensoterraCoordinator(hass, api)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
