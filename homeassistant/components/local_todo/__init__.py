"""The Local To-do integration."""

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import slugify

from .const import CONF_STORAGE_KEY, CONF_TODO_LIST_NAME, DOMAIN
from .store import LocalTodoListStore

PLATFORMS: list[Platform] = [Platform.TODO]

STORAGE_PATH = ".storage/local_todo.{key}.ics"

type LocalTodoConfigEntry = ConfigEntry[LocalTodoListStore]


async def async_setup_entry(hass: HomeAssistant, entry: LocalTodoConfigEntry) -> None:
    """Set up Local To-do from a config entry."""
    path = Path(hass.config.path(STORAGE_PATH.format(key=entry.data[CONF_STORAGE_KEY])))
    store = LocalTodoListStore(hass, path)
    try:
        await store.async_load()
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="load_file_error",
            translation_placeholders={"path": str(path)},
        ) from err

    entry.runtime_data = store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    key = slugify(entry.data[CONF_TODO_LIST_NAME])
    path = Path(hass.config.path(STORAGE_PATH.format(key=key)))

    def unlink(path: Path) -> None:
        path.unlink(missing_ok=True)

    await hass.async_add_executor_job(unlink, path)
