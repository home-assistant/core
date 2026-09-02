"""Storage handers."""

import json
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.util import json as json_util

from ..const import VERSION_STORAGE
from ..exceptions import HacsException
from .logger import LOGGER

_LOGGER = LOGGER

STORE_CACHE_KEY = "hacs_store_cache"


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
    return key if "/" in key else f"hacs.{key}"


def _get_store_for_key(
    hass: HomeAssistant, key: str, encoder: type[json.JSONEncoder]
) -> HACSStore:
    """Create a Store object for the key."""
    return HACSStore(
        hass,
        VERSION_STORAGE,  # type: ignore[arg-type] # the store keeps its version as a string
        get_store_key(key),
        encoder=encoder,
        atomic_writes=True,
    )


def get_store_for_key(hass: HomeAssistant, key: str) -> HACSStore:
    """Get (or create and cache) the Store object for the key.

    The cache is cleared in async_unload_entry so Store instances do not
    survive an integration unload / reload.
    """
    cache = hass.data.setdefault(STORE_CACHE_KEY, {})
    if key not in cache:
        cache[key] = _get_store_for_key(hass, key, JSONEncoder)
    return cache[key]


async def async_load_from_store(hass: HomeAssistant, key: str) -> Any:
    """Load the retained data from store and return de-serialized data."""
    return await get_store_for_key(hass, key).async_load() or {}


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
    await get_store_for_key(hass, key).async_remove()
