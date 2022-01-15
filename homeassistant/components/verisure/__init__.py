"""Support for Verisure devices."""
from __future__ import annotations

from contextlib import suppress
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from .const import DOMAIN
from .coordinator import VerisureDataUpdateCoordinator

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Verisure from a config entry."""
    coordinator = VerisureDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        raise ConfigEntryAuthFailed

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_logout)
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


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
