"""The Local Calendar integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import slugify

from .const import CONF_CALENDAR_NAME, CONF_STORAGE_KEY, DOMAIN
from .store import LocalCalendarStore

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CALENDAR]

STORAGE_PATH = ".storage/local_calendar.{key}.ics"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Local Calendar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if CONF_STORAGE_KEY not in entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_STORAGE_KEY: slugify(entry.data[CONF_CALENDAR_NAME]),
            },
        )

    path = Path(hass.config.path(STORAGE_PATH.format(key=entry.data[CONF_STORAGE_KEY])))
    store = LocalCalendarStore(hass, path)
    try:
        await store.async_load()
    except OSError as err:
        raise ConfigEntryNotReady("Failed to load file {path}: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    key = slugify(entry.data[CONF_CALENDAR_NAME])
    path = Path(hass.config.path(STORAGE_PATH.format(key=key)))

    def unlink(path: Path) -> None:
        path.unlink(missing_ok=True)

    await hass.async_add_executor_job(unlink, path)
