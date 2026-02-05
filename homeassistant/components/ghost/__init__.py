"""The Ghost integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aioghost import GhostAdminAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ADMIN_API_KEY, CONF_API_URL, DOMAIN as DOMAIN
from .coordinator import GhostDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GhostConfigEntry = ConfigEntry[GhostRuntimeData]


@dataclass
class GhostRuntimeData:
    """Runtime data for Ghost integration."""

    coordinator: GhostDataUpdateCoordinator
    api: GhostAdminAPI


async def async_setup_entry(hass: HomeAssistant, entry: GhostConfigEntry) -> bool:
    """Set up Ghost from a config entry."""
    api_url = entry.data[CONF_API_URL]
    admin_api_key = entry.data[CONF_ADMIN_API_KEY]

    api = GhostAdminAPI(api_url, admin_api_key, session=async_get_clientsession(hass))

    coordinator = GhostDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GhostRuntimeData(coordinator=coordinator, api=api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GhostConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
