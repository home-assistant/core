"""Roborock storage."""

import dataclasses
import logging
from pathlib import Path
import shutil
from typing import Any

from roborock.devices.cache import Cache, CacheData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_PATH = f".storage/{DOMAIN}"
MAPS_PATH = "maps"
CACHE_VERSION = 1


def _storage_path_prefix(hass: HomeAssistant, entry_id: str) -> Path:
    """Storage path for the old map storage cache location."""
    return Path(hass.config.path(STORAGE_PATH)) / entry_id


async def async_remove_map_storage(hass: HomeAssistant, entry_id: str) -> None:
    """Remove all map storage associated with a config entry.

    This removes all on-disk map files for the given config entry. This is the
    old format that was replaced by the `CacheStore` implementation.
    """

    def remove(path_prefix: Path) -> None:
        try:
            if path_prefix.exists():
                shutil.rmtree(path_prefix, ignore_errors=True)
        except OSError as err:
            _LOGGER.error("Unable to remove map files in %s: %s", path_prefix, err)

    path_prefix = _storage_path_prefix(hass, entry_id)
    _LOGGER.debug("Removing maps from disk store: %s", path_prefix)
    await hass.async_add_executor_job(remove, path_prefix)


class CacheStore(Cache):
    """Store and retrieve cache for a Roborock device.

    This implements the roborock Cache interface, backend by a Home Assistant
    Store that can be flushed to disk. This also manages dispatching the
    roborock map contents to separate on disk files via RoborockMapStorage
    since maps can be large.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize CacheStore."""
        self._cache_store = Store[dict[str, Any]](
            hass,
            version=CACHE_VERSION,
            key=f"{DOMAIN}/{entry_id}",
            private=True,
        )
        self._cache_data: CacheData | None = None

    async def get(self) -> CacheData:
        """Retrieve cached metadata."""
        if self._cache_data is None:
            if data := await self._cache_store.async_load():
                self._cache_data = CacheData(**data)
            else:
                self._cache_data = CacheData()

        return self._cache_data

    async def set(self, value: CacheData) -> None:
        """Save cached metadata."""
        self._cache_data = value

    async def flush(self) -> None:
        """Flush cached metadata to disk."""
        if self._cache_data is not None:
            await self._cache_store.async_save(dataclasses.asdict(self._cache_data))

    async def async_remove(self) -> None:
        """Remove cached metadata from disk."""
        await self._cache_store.async_remove()
