"""Platform for the iZone AC."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_CONFIG, DOMAIN
from .discovery import async_start_discovery_service, async_stop_discovery_service

PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the iZone component config."""

    # Check for manually added config, this may exclude some devices
    if conf := config.get(DOMAIN):
        hass.data[DATA_CONFIG] = conf

        # Explicitly added in the config file, create a config entry.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    had_loaded_entries = any(
        config_entry.state
        in (
            config_entries.ConfigEntryState.LOADED,
            config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
        )
        for config_entry in hass.config_entries.async_entries(IZONE)
        if config_entry.entry_id != entry.entry_id
    )
    await async_start_discovery_service(hass)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        if not had_loaded_entries:
            await async_stop_discovery_service(hass)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and stop discovery process."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and not any(
        config_entry.state
        in (
            config_entries.ConfigEntryState.LOADED,
            config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
        )
        for config_entry in hass.config_entries.async_entries(IZONE)
    ):
        await async_stop_discovery_service(hass)

    return unload_ok
