"""The Rako integration."""
from __future__ import annotations

from asyncio import Task
import logging
from typing import TypedDict

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .bridge import RakoBridge
from .const import DOMAIN
from .light import RakoLight

_LOGGER = logging.getLogger(__name__)


class RakoDomainEntryData(TypedDict):
    """A single Rako config entry's data."""

    rako_bridge_client: RakoBridge
    rako_light_map: dict[str, RakoLight]
    rako_listener_task: Task | None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rako from a config entry."""

    rako_bridge = RakoBridge(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.entry_id,
        hass,
    )

    hass.data.setdefault(DOMAIN, {})
    rako_domain_entry_data: RakoDomainEntryData = {
        "rako_bridge_client": rako_bridge,
        "rako_light_map": {},
        "rako_listener_task": None,
    }
    hass.data[DOMAIN][entry.entry_id] = rako_domain_entry_data

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, LIGHT_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, LIGHT_DOMAIN)

    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True
