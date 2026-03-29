"""mijn.ista.nl — ista Nederland Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from mijn_ista_api import MijnIstaAPI
from .coordinator import MijnIstaCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type MijnIstaConfigEntry = ConfigEntry[MijnIstaCoordinator]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry versions.

    v1 → v2: drop the stored ``language`` field (language is now derived from
    ``hass.config.language`` at runtime, not stored per-entry).
    """
    if config_entry.version < 2:
        _LOGGER.debug("Migrating mijn_ista config entry to version 2")
        hass.config_entries.async_update_entry(
            config_entry,
            data={k: v for k, v in config_entry.data.items() if k != "language"},
            version=2,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MijnIstaConfigEntry) -> bool:
    """Set up mijn.ista.nl from a config entry."""
    session = async_get_clientsession(hass)
    # Derive API language from the HA language setting.
    api_lang = "nl-NL" if hass.config.language.startswith("nl") else "en-GB"
    api = MijnIstaAPI(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        lang=api_lang,
    )
    coordinator = MijnIstaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MijnIstaConfigEntry) -> bool:
    """Unload a mijn.ista.nl config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: MijnIstaConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
