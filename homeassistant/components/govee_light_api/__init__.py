"""The Govee Lights - Local API integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import GoveeLocalApiCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Local API from a config entry."""

    entry_id = entry.entry_id
    coordinator: GoveeLocalApiCoordinator = hass.data.setdefault(DOMAIN, {}).get(
        entry_id, None
    )

    if not coordinator:
        coordinator = GoveeLocalApiCoordinator(
            hass=hass,
            config_entry=entry,
            logger=_LOGGER,
        )

        hass.data.setdefault(DOMAIN, {})[entry_id] = coordinator
        await coordinator.start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_id = entry.entry_id

    coordinator: GoveeLocalApiCoordinator = hass.data.setdefault(DOMAIN, {}).get(
        entry_id
    )
    if coordinator:
        coordinator.clenaup()
        del hass.data[DOMAIN][entry_id]
        del hass.data[DOMAIN]

    return True
