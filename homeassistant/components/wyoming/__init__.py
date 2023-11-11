"""The Wyoming integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import ATTR_SPEAKER, DOMAIN
from .data import WyomingService

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "ATTR_SPEAKER",
    "DOMAIN",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load Wyoming."""
    service = await WyomingService.create(entry.data["host"], entry.data["port"])

    if service is None:
        raise ConfigEntryNotReady("Unable to connect")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = service

    await hass.config_entries.async_forward_entry_setups(
        entry,
        service.platforms,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Wyoming."""
    service: WyomingService = hass.data[DOMAIN][entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        service.platforms,
    )
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
