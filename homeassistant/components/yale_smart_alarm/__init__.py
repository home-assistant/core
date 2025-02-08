"""The yale_smart_alarm component."""

from __future__ import annotations

from homeassistant.components.lock import CONF_DEFAULT_CODE, DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import LOGGER, PLATFORMS
from .coordinator import YaleDataUpdateCoordinator

type YaleConfigEntry = ConfigEntry[YaleDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: YaleConfigEntry) -> bool:
    """Set up Yale from a config entry."""

    coordinator = YaleDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: YaleConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: YaleConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: YaleConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_options = entry.options.copy()
        if config_entry_default_code := entry.options.get(CONF_CODE):
            entity_reg = er.async_get(hass)
            entries = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
            for entity in entries:
                if entity.entity_id.startswith("lock"):
                    entity_reg.async_update_entity_options(
                        entity.entity_id,
                        LOCK_DOMAIN,
                        {CONF_DEFAULT_CODE: config_entry_default_code},
                    )
            del new_options[CONF_CODE]

        hass.config_entries.async_update_entry(entry, options=new_options, version=2)

    if entry.version == 2 and entry.minor_version == 1:
        # Removes name from entry data
        new_data = entry.data.copy()
        del new_data[CONF_NAME]
        hass.config_entries.async_update_entry(entry, data=new_data, minor_version=2)

    LOGGER.debug("Migration to version %s successful", entry.version)

    return True
