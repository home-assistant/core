"""The Local Calendar integration."""

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import slugify

from .const import CONF_CALENDAR_NAME, CONF_STORAGE_KEY, STORAGE_PATH
from .store import LocalCalendarStore

PLATFORMS: list[Platform] = [Platform.CALENDAR]

type LocalCalendarConfigEntry = ConfigEntry[LocalCalendarStore]


async def async_setup_entry(
    hass: HomeAssistant, entry: LocalCalendarConfigEntry
) -> None:
    """Set up Local Calendar from a config entry."""
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
        raise ConfigEntryNotReady(f"Failed to load file {path}: {err}") from err

    entry.runtime_data = store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: LocalCalendarConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: LocalCalendarConfigEntry
) -> None:
    """Handle removal of an entry."""
    key = slugify(entry.data[CONF_CALENDAR_NAME])
    path = Path(hass.config.path(STORAGE_PATH.format(key=key)))

    def unlink(path: Path) -> None:
        path.unlink(missing_ok=True)

    await hass.async_add_executor_job(unlink, path)
