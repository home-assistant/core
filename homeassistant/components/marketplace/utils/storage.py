"""Storage handlers."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.util import json as json_util
from homeassistant.util.hass_dict import HassKey

from ..const import VERSION_STORAGE
from ..exceptions import MarketplaceError
from .logger import LOGGER
from .path import resolve_in_directory

_LOGGER = LOGGER

STORENAME = "marketplace"

# The keys the custom integration wrote its data under, mapped to the key each
# one is adopted as on the first load. They are removed once adopted.
LEGACY_STORAGE_KEYS: dict[str, str] = {
    "common": "hacs.hacs",
    "critical": "hacs.critical",
    "repositories": "hacs.repositories",
}

# The data file older releases wrote. Read as a last resort, never adopted,
# and removed once the Marketplace has a repositories file of its own.
LEGACY_DATA_STORAGE_KEY = "hacs.data"

# Older releases kept a file per downloaded repository, removed on uninstall.
LEGACY_HACS_REPOSITORY_STORAGE_KEY = "hacs/{repository_id}.hacs"


class MarketplaceStorage(Store[dict[str, Any]]):
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
            raise MarketplaceError(exception) from exception
        if data == {} or data["version"] != self.version:
            return None
        return data["data"]


STORAGE_CACHE_KEY: HassKey[dict[str, MarketplaceStorage]] = HassKey(
    "marketplace_storage_cache"
)


def get_storage_key(key: str) -> str:
    """Return the key to use with homeassistant.helpers.storage.Storage."""
    return key if "/" in key else f"{STORENAME}.{key}"


def _create_storage(hass: HomeAssistant, storage_key: str) -> MarketplaceStorage:
    """Create a Store object for a resolved storage key."""
    return MarketplaceStorage(
        hass,
        VERSION_STORAGE,  # type: ignore[arg-type] # the Marketplace keeps its version as a string
        storage_key,
        encoder=JSONEncoder,
        atomic_writes=True,
    )


def get_storage_for_key(hass: HomeAssistant, key: str) -> MarketplaceStorage:
    """Get (or create and cache) the Store object for the key.

    The cache is cleared in async_unload_entry so Store instances do not
    survive an integration unload / reload.
    """
    cache = hass.data.setdefault(STORAGE_CACHE_KEY, {})
    if key not in cache:
        cache[key] = _create_storage(hass, get_storage_key(key))
    return cache[key]


async def _async_adopt_legacy_data(
    hass: HomeAssistant, key: str, marketplace: MarketplaceStorage
) -> Any:
    """Copy the data the custom integration wrote for this key over to our own key.

    Only reached while we have no file of our own, so an installation that came
    from the custom integration picks up where it left off.
    """
    if (legacy_key := LEGACY_STORAGE_KEYS.get(key)) is None:
        return None

    if (data := await _create_storage(hass, legacy_key).async_load()) is None:
        return None

    _LOGGER.info("Adopting the data in '%s' as '%s'", legacy_key, get_storage_key(key))
    await marketplace.async_save(data)
    return data


async def async_load_from_storage(hass: HomeAssistant, key: str) -> Any:
    """Load the retained data from store and return de-serialized data."""
    marketplace = get_storage_for_key(hass, key)
    if (data := await marketplace.async_load()) is not None:
        return data or {}
    return await _async_adopt_legacy_data(hass, key, marketplace) or {}


async def async_load_legacy_data(hass: HomeAssistant) -> Any:
    """Load the data file older releases wrote.

    Read only, this file is never adopted under one of our own keys.
    """
    return await _create_storage(hass, LEGACY_DATA_STORAGE_KEY).async_load() or {}


async def async_save_to_storage(hass: HomeAssistant, key: str, data: Any) -> None:
    """Generate dynamic data to store and save it to the filesystem.

    The data is only written if the content on the disk has changed
    by reading the existing content and comparing it.

    If the data has changed this will generate two executor jobs

    If the data has not changed this will generate one executor job
    """
    current = await async_load_from_storage(hass, key)
    if current is None or current != data:
        await get_storage_for_key(hass, key).async_save(data)
        return
    _LOGGER.debug(
        "Did not store data for '%s', the content did not change",
        get_storage_key(key),
    )


async def async_remove_storage(hass: HomeAssistant, key: str) -> None:
    """Remove a store element that should no longer be used."""
    if "/" not in key:
        return

    marketplace = get_storage_for_key(hass, key)

    # The key carries a repository id, so the file it resolves to is checked
    # before anything is unlinked.
    resolve_in_directory(hass.config.path(STORAGE_DIR), marketplace.path)

    await marketplace.async_remove()
