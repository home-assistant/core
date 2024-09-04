"""Support for Verisure devices."""

from __future__ import annotations

from contextlib import suppress
import os
from pathlib import Path

from homeassistant.components.lock import CONF_DEFAULT_CODE, DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_LOCK_DEFAULT_CODE, DOMAIN, LOGGER
from .coordinator import VerisureDataUpdateCoordinator

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Verisure from a config entry."""
    await hass.async_add_executor_job(migrate_cookie_files, hass, entry)

    coordinator = VerisureDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        raise ConfigEntryNotReady("Could not log in to verisure.")

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Migrate lock default code from config entry to lock entity

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Update options
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    # Propagate configuration change.
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.async_update_listeners()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Verisure config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    cookie_file = hass.config.path(STORAGE_DIR, f"verisure_{entry.entry_id}")
    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(os.unlink, cookie_file)

    del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True


def migrate_cookie_files(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old cookie file to new location."""
    cookie_file = Path(hass.config.path(STORAGE_DIR, f"verisure_{entry.unique_id}"))
    if cookie_file.exists():
        cookie_file.rename(
            hass.config.path(STORAGE_DIR, f"verisure_{entry.data[CONF_EMAIL]}")
        )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        if config_entry_default_code := entry.options.get(CONF_LOCK_DEFAULT_CODE):
            entity_reg = er.async_get(hass)
            entries = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
            for entity in entries:
                if entity.entity_id.startswith("lock"):
                    entity_reg.async_update_entity_options(
                        entity.entity_id,
                        LOCK_DOMAIN,
                        {CONF_DEFAULT_CODE: config_entry_default_code},
                    )
            new_options = entry.options.copy()
            del new_options[CONF_LOCK_DEFAULT_CODE]

            hass.config_entries.async_update_entry(entry, options=new_options)

        hass.config_entries.async_update_entry(entry, version=2)

    LOGGER.info("Migration to version %s successful", entry.version)

    return True
