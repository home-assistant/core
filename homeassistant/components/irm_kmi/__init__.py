"""Integration for IRM KMI weather."""

import logging

from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, IRM_KMI_TO_HA_CONDITION_MAP, PLATFORMS, USER_AGENT
from .coordinator import IrmKmiCoordinator
from .data import IrmKmiConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})

    entry.runtime_data = IrmKmiApiClientHa(
        session=async_get_clientsession(hass),
        user_agent=USER_AGENT,
        cdt_map=IRM_KMI_TO_HA_CONDITION_MAP,
    )

    hass.data[DOMAIN][entry.entry_id] = irm_kmi_coordinator = IrmKmiCoordinator(
        hass, entry
    )

    # When integration is set up, set the logging level of the irm_kmi_api package to the same level to help debugging.
    logging.getLogger("irm_kmi_api").setLevel(_LOGGER.getEffectiveLevel())
    try:
        await irm_kmi_coordinator.async_config_entry_first_refresh()
    except ConfigEntryError:
        # This happens when the zone is out of Benelux (no forecast available there).
        # This should be caught by the config flow anyway.
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: IrmKmiConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(
    _hass: HomeAssistant, _config_entry: IrmKmiConfigEntry
) -> bool:
    """Migrate old entry."""
    # There are no previous versions of the config entry at this time.
    return True
