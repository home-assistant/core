"""Integration for IRM KMI weather."""

import logging

from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import IRM_KMI_TO_HA_CONDITION_MAP, PLATFORMS, USER_AGENT
from .coordinator import IrmKmiCoordinator
from .types import IrmKmiConfigEntry, IrmKmiData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> bool:
    """Set up this integration using UI."""
    api_client = IrmKmiApiClientHa(
        session=async_get_clientsession(hass),
        user_agent=USER_AGENT,
        cdt_map=IRM_KMI_TO_HA_CONDITION_MAP,
    )

    entry.runtime_data = IrmKmiData(
        api_client=api_client,
        # If I don't put the api_client in the coordinator this way, I get circular dependencies.
        coordinator=IrmKmiCoordinator(hass, entry, api_client),
    )

    try:
        await entry.runtime_data.coordinator.async_config_entry_first_refresh()
    except ConfigEntryError:
        # This happens when the zone is out of Benelux (no forecast available there).
        # This should be caught by the config flow anyway.
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
