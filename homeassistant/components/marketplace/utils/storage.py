"""Storage handlers."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.util import json as json_util
from homeassistant.util.hass_dict import HassKey

from ..const import LEGACY_HACS_STORAGE_VERSION, STORAGE_VERSION
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

# Older releases kept every repository in this file, grouped by category. The
# custom integration still falls back to it when its repositories file is empty.
LEGACY_DATA_KEY = "hacs.data"

# Older releases kept a file per installed repository, removed on uninstall.
LEGACY_HACS_REPOSITORY_STORAGE_KEY = "hacs/{repository_id}.hacs"


STORAGE_CACHE_KEY: HassKey[dict[str, Store[Any]]] = HassKey("marketplace_storage_cache")


def get_storage_key(key: str) -> str:
    """Return the key to use with homeassistant.helpers.storage.Storage."""
    return key if "/" in key else f"{STORENAME}.{key}"


def get_storage_for_key(hass: HomeAssistant, key: str) -> Store[Any]:
    """Get (or create and cache) the Store object for the key.

    The cache is cleared in async_unload_entry so Store instances do not
    survive an integration unload / reload.
    """
    cache = hass.data.setdefault(STORAGE_CACHE_KEY, {})
    if key not in cache:
        cache[key] = Store(
            hass,
            STORAGE_VERSION,
            get_storage_key(key),
            encoder=JSONEncoder,
            atomic_writes=True,
            # The repositories file is large, encoding it stays off the event loop
            serialize_in_event_loop=False,
        )
    return cache[key]


def _load_legacy_file(path: str) -> Any:
    """Read a storage file of the custom integration, None if there is none.

    Its string version is not something the Store helper can read.
    """
    data = json_util.load_json(path)
    if not isinstance(data, dict) or data.get("version") != LEGACY_HACS_STORAGE_VERSION:
        return None
    return data.get("data")


def _load_legacy_repositories_from_data(path: str) -> dict[str, Any] | None:
    """Read the repositories from the older combined file, keyed by their id."""
    if not isinstance(data := _load_legacy_file(path), dict):
        return None

    repositories: dict[str, Any] = {}
    for category, entries in (data.get("repositories") or {}).items():
        for repository in entries:
            repositories[str(repository["id"])] = {"category": category, **repository}
    return repositories


async def _async_adopt_legacy_data(
    hass: HomeAssistant, key: str, marketplace: Store[Any]
) -> Any:
    """Copy the data the custom integration wrote for this key over to our own key.

    Only reached while we have no file of our own, so an installation that came
    from the custom integration picks up where it left off.
    """
    if (legacy_key := LEGACY_STORAGE_KEYS.get(key)) is None:
        return None

    legacy_path = hass.config.path(STORAGE_DIR, legacy_key)
    data = await hass.async_add_executor_job(_load_legacy_file, legacy_path)

    if key == "repositories" and not data:
        legacy_key = LEGACY_DATA_KEY
        data = await hass.async_add_executor_job(
            _load_legacy_repositories_from_data,
            hass.config.path(STORAGE_DIR, legacy_key),
        )

    if not data:
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
    await hass.async_add_executor_job(
        resolve_in_directory, hass.config.path(STORAGE_DIR), marketplace.path
    )

    await marketplace.async_remove()
