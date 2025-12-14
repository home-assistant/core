"""Roborock storage."""

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
CACHE_VERSION = 2


def _storage_path_prefix(hass: HomeAssistant, entry_id: str) -> Path:
    """Storage path for the old map storage cache location."""
    return Path(hass.config.path(STORAGE_PATH)) / entry_id


async def async_cleanup_map_storage(hass: HomeAssistant, entry_id: str) -> None:
    """Remove map storage in the old format, if any.

    This removes all on-disk map files for the given config entry. This is the
    old format that was replaced by the `CacheStore` implementation.
    """

    def remove(path_prefix: Path) -> None:
        try:
            if path_prefix.exists() and path_prefix.is_dir():
                _LOGGER.debug("Removing maps from disk store: %s", path_prefix)
                shutil.rmtree(path_prefix, ignore_errors=True)
        except OSError as err:
            _LOGGER.error("Unable to remove map files in %s: %s", path_prefix, err)

    path_prefix = _storage_path_prefix(hass, entry_id)
    await hass.async_add_executor_job(remove, path_prefix)


class StoreImpl(Store[dict[str, Any]]):
    """Store implementation for Roborock cache."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize StoreImpl."""
        super().__init__(
            hass,
            version=CACHE_VERSION,
            key=f"{DOMAIN}/{entry_id}",
            private=True,
        )

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Wipe out old caches with the old format."""
        if old_major_version == 1:
            # No need for migration as version 1 was never in any stable releases
            return {}
        return old_data


class CacheStore(Cache):
    """Store and retrieve cache for a Roborock device.

    This implements the roborock Cache interface, backend by a Home Assistant
    Store that can be flushed to disk. This also manages dispatching the
    roborock map contents to separate on disk files via RoborockMapStorage
    since maps can be large.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize CacheStore."""
        self._cache_store = StoreImpl(hass, entry_id)
        self._cache_data: CacheData | None = None

    async def get(self) -> CacheData:
        """Retrieve cached metadata."""
        if self._cache_data is None:
            if data := await self._cache_store.async_load():
                self._cache_data = CacheData.from_dict(data)
            else:
                self._cache_data = CacheData()

        return self._cache_data

    async def set(self, value: CacheData) -> None:
        """Save cached metadata."""
        self._cache_data = value

    async def flush(self) -> None:
        """Flush cached metadata to disk."""
        if self._cache_data is not None:
            await self._cache_store.async_save(self._cache_data.as_dict())

    async def async_remove(self) -> None:
        """Remove cached metadata from disk."""
        await self._cache_store.async_remove()
