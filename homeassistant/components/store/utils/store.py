"""Storage handers."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.util import json as json_util

from ..const import VERSION_STORAGE
from ..exceptions import HacsException
from .logger import LOGGER
from .path import resolve_in_directory

_LOGGER = LOGGER

STORENAME = "store"
STORE_CACHE_KEY = "hacs_store_cache"

# The keys HACS wrote its data under, mapped to the key each one is adopted as
# on the first load. The HACS files themselves are never written to or removed:
# they are what a user rolls back to.
LEGACY_STORE_KEYS: dict[str, str] = {
    "common": "hacs.hacs",
    "critical": "hacs.critical",
    "repositories": "hacs.repositories",
}

# The data file older HACS releases wrote. Read as a last resort, never adopted.
LEGACY_DATA_STORE_KEY = "hacs.data"


class HACSStore(Store[dict[str, Any]]):
    """A subclass of Store that allows multiple loads in the executor."""

    def load(self) -> Any:
        """Load the data from disk if version matches."""
        try:
            data: Any = json_util.load_json(self.path)
        except HomeAssistantError as exception:
            _LOGGER.critical(
                "Could not load '%s', restore it from a backup or delete the file: %s",
                self.path,
                exception,
            )
            raise HacsException(exception) from exception
        if data == {} or data["version"] != self.version:
            return None
        return data["data"]


def get_store_key(key: str) -> str:
    """Return the key to use with homeassistant.helpers.storage.Storage."""
    return key if "/" in key else f"{STORENAME}.{key}"


def _create_store(hass: HomeAssistant, store_key: str) -> HACSStore:
    """Create a Store object for a resolved storage key."""
    return HACSStore(
        hass,
        VERSION_STORAGE,  # type: ignore[arg-type] # the store keeps its version as a string
        store_key,
        encoder=JSONEncoder,
        atomic_writes=True,
    )


def get_store_for_key(hass: HomeAssistant, key: str) -> HACSStore:
    """Get (or create and cache) the Store object for the key.

    The cache is cleared in async_unload_entry so Store instances do not
    survive an integration unload / reload.
    """
    cache = hass.data.setdefault(STORE_CACHE_KEY, {})
    if key not in cache:
        cache[key] = _create_store(hass, get_store_key(key))
    return cache[key]


async def _async_adopt_hacs_data(
    hass: HomeAssistant, key: str, store: HACSStore
) -> Any:
    """Copy the data HACS wrote for this key over to our own key.

    Only reached while we have no file of our own, so an installation that used
    to run HACS picks up where HACS left off.
    """
    if (legacy_key := LEGACY_STORE_KEYS.get(key)) is None:
        return None

    if (data := await _create_store(hass, legacy_key).async_load()) is None:
        return None

    _LOGGER.info("Adopting the data in '%s' as '%s'", legacy_key, get_store_key(key))
    await store.async_save(data)
    return data


async def async_load_from_store(hass: HomeAssistant, key: str) -> Any:
    """Load the retained data from store and return de-serialized data."""
    store = get_store_for_key(hass, key)
    if (data := await store.async_load()) is not None:
        return data or {}
    return await _async_adopt_hacs_data(hass, key, store) or {}


async def async_load_legacy_data(hass: HomeAssistant) -> Any:
    """Load the data file older HACS releases wrote.

    Read only, this file is never adopted under one of our own keys.
    """
    return await _create_store(hass, LEGACY_DATA_STORE_KEY).async_load() or {}


async def async_save_to_store(hass: HomeAssistant, key: str, data: Any) -> None:
    """Generate dynamic data to store and save it to the filesystem.

    The data is only written if the content on the disk has changed
    by reading the existing content and comparing it.

    If the data has changed this will generate two executor jobs

    If the data has not changed this will generate one executor job
    """
    current = await async_load_from_store(hass, key)
    if current is None or current != data:
        await get_store_for_key(hass, key).async_save(data)
        return
    _LOGGER.debug(
        "<HACSStore async_save_to_store> Did not store data for '%s'. Content did not change",
        get_store_key(key),
    )


async def async_remove_store(hass: HomeAssistant, key: str) -> None:
    """Remove a store element that should no longer be used."""
    if "/" not in key:
        return

    store = get_store_for_key(hass, key)

    # The key carries a repository id, so the file it resolves to is checked
    # before anything is unlinked.
    resolve_in_directory(hass.config.path(STORAGE_DIR), store.path)

    await store.async_remove()
