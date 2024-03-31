"""Roborock storage."""

import asyncio
import dataclasses
import logging
import os
import time

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MAP_PATH = f"{DOMAIN}/maps"
MAP_UPDATE_FREQUENCY = 3600  # Only save the map once every hour.


async def get_roborock_storage(hass: HomeAssistant, entry_id: str):
    """Get a roborock storage object for a given config entry."""
    map_path = hass.config.path(MAP_PATH)

    def mkdir() -> None:
        os.makedirs(map_path, exist_ok=True)

    await hass.async_add_executor_job(mkdir)
    return RoborockStorage(hass, map_path, entry_id)


@dataclasses.dataclass
class RoborockMapEntry:
    """Describe a map entry stored on disk."""

    map_name: str
    content: bytes
    time: float


class RoborockStorage:
    """Store Roborock data."""

    def __init__(
        self,
        hass: HomeAssistant,
        map_path: str,
        entry_id: str,
    ) -> None:
        """Initialize RoborockStorage."""
        self._hass = hass
        self._data: dict[str, RoborockMapEntry] = {}
        self._map_path = map_path
        self._entry_id = entry_id

    def _should_update(self, map_entry: RoborockMapEntry | None, content: bytes):
        return (
            map_entry is None
            or time.time() - map_entry.time > MAP_UPDATE_FREQUENCY
            or content != map_entry.content
        )

    def _get_map_filename(self, map_name: str):
        return self._hass.config.path(f"{MAP_PATH}/{self._entry_id}/{map_name}")

    async def async_load_map(self, map_name: str) -> bytes | None:
        """Load map content."""
        filename = self._get_map_filename(map_name)

        def load_map(filename: str) -> bytes | None:
            if not os.path.exists(filename):
                return None
            _LOGGER.debug("Reading map from disk store: %s", filename)
            with open(filename, "rb") as stored_map:
                return stored_map.read()

        try:
            map_data = await self._hass.async_add_executor_job(load_map, filename)
        except OSError as err:
            _LOGGER.error("Unable to read map file: %s %s", filename, err)
            return None
        if map_data is None:
            return None
        self._data[map_name] = RoborockMapEntry(
            map_name,
            map_data,
            time.time(),
        )
        return self._data[map_name].content

    async def async_save_map(self, map_name: str, content: bytes) -> None:
        """Write map if it should be updated."""
        map_entry = self._data.get(map_name)
        if not self._should_update(map_entry, content):
            return None
        filename = self._get_map_filename(map_name)

        def save_map(filename: str, content: bytes) -> None:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            _LOGGER.debug("Saving event map to disk store: %s", filename)
            with open(filename, "wb") as stored_map:
                stored_map.write(content)

        try:
            await self._hass.async_add_executor_job(save_map, filename, content)
        except OSError as err:
            _LOGGER.error("Unable to write map file: %s %s", filename, err)
        else:
            self._data[map_name] = RoborockMapEntry(map_name, content, time.time())

    async def async_remove_maps(self, entry_id: str) -> None:
        """Remove all maps associated with a config entry."""

        def remove_map(filename: str) -> None:
            _LOGGER.debug("Removing map from disk store: %s", filename)
            os.remove(filename)

        try:
            await asyncio.gather(
                *(
                    self._hass.async_add_executor_job(
                        remove_map, self._get_map_filename(file)
                    )
                    for file in os.listdir(
                        self._hass.config.path(f"{MAP_PATH}/{entry_id}")
                    )
                )
            )
        except OSError as err:
            _LOGGER.error("Unable to remove map files for: %s %s", entry_id, err)
