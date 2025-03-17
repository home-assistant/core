"""Roborock storage."""

import logging
from pathlib import Path
import shutil

from homeassistant.core import HomeAssistant

from .const import DOMAIN, MAP_FILENAME_SUFFIX

_LOGGER = logging.getLogger(__name__)

STORAGE_PATH = f".storage/{DOMAIN}"
MAPS_PATH = "maps"


def _storage_path_prefix(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(STORAGE_PATH)) / entry_id


class RoborockMapStorage:
    """Store and retrieve maps for a Roborock device.

    An instance of RoborockMapStorage is created for each device and manages
    local storage of maps for that device.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str, device_id_slug: str) -> None:
        """Initialize RoborockMapStorage."""
        self._hass = hass
        self._path_prefix = (
            _storage_path_prefix(hass, entry_id) / MAPS_PATH / device_id_slug
        )
        self._write_queue: dict[int, bytes] = {}

    async def async_load_map(self, map_flag: int) -> bytes | None:
        """Load maps from disk."""
        filename = self._path_prefix / f"{map_flag}{MAP_FILENAME_SUFFIX}"
        return await self._hass.async_add_executor_job(self._load_map, filename)

    def _load_map(self, filename: Path) -> bytes | None:
        """Load maps from disk."""
        if not filename.exists():
            return None
        try:
            return filename.read_bytes()
        except OSError as err:
            _LOGGER.debug("Unable to read map file: %s %s", filename, err)
            return None

    async def async_save_map(self, map_flag: int, content: bytes) -> None:
        """Save the map to a pending write queue."""
        self._write_queue[map_flag] = content

    async def flush(self) -> None:
        """Flush all maps to disk."""
        _LOGGER.debug("Flushing %s maps to disk", len(self._write_queue))

        queue = self._write_queue.copy()

        def _flush_all() -> None:
            for map_flag, content in queue.items():
                filename = self._path_prefix / f"{map_flag}{MAP_FILENAME_SUFFIX}"
                self._save_map(filename, content)

        await self._hass.async_add_executor_job(_flush_all)
        self._write_queue.clear()

    def _save_map(self, filename: Path, content: bytes) -> None:
        """Write the map to disk."""
        _LOGGER.debug("Saving map to disk: %s", filename)
        try:
            filename.parent.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            _LOGGER.error("Unable to create map directory: %s %s", filename, err)
            return
        try:
            filename.write_bytes(content)
        except OSError as err:
            _LOGGER.error("Unable to write map file: %s %s", filename, err)


async def async_remove_map_storage(hass: HomeAssistant, entry_id: str) -> None:
    """Remove all map storage  associated with a config entry."""

    def remove(path_prefix: Path) -> None:
        try:
            if path_prefix.exists():
                shutil.rmtree(path_prefix, ignore_errors=True)
        except OSError as err:
            _LOGGER.error("Unable to remove map files in %s: %s", path_prefix, err)

    path_prefix = _storage_path_prefix(hass, entry_id)
    _LOGGER.debug("Removing maps from disk store: %s", path_prefix)
    await hass.async_add_executor_job(remove, path_prefix)
