"""Integration for IRM KMI weather."""

import logging

from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONFIG_FLOW_VERSION,
    DOMAIN,
    IRM_KMI_TO_HA_CONDITION_MAP,
    PLATFORMS,
    USER_AGENT,
)
from .coordinator import IrmKmiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = irm_kmi_coordinator = IrmKmiCoordinator(
        hass, entry
    )

    entry.runtime_data = IrmKmiApiClientHa(
        session=async_get_clientsession(hass),
        user_agent=USER_AGENT,
        cdt_map=IRM_KMI_TO_HA_CONDITION_MAP,
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(_hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %d", config_entry.version)

    if config_entry.version > CONFIG_FLOW_VERSION - 1:
        # This means the user has downgraded from a future version.
        _LOGGER.error(
            "Downgrading configuration is not supported: your config version is %d, "
            "the current version used by the integration is %d",
            config_entry.version,
            CONFIG_FLOW_VERSION,
        )
        return False

    _LOGGER.debug("Migration to version %d successful", config_entry.version)

    return True
