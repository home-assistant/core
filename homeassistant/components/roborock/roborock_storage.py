import logging
import os
from typing import Any
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)
MAP_PATHS = f"{DOMAIN}/roborock/maps"
STORAGE_KEY = "roborock.storage"
STORAGE_VERSION = 1


async def get_roborock_storage(hass: HomeAssistant):
    map_path = hass.config.path(MAP_PATHS)

    def mkdir() -> None:
        os.makedirs(map_path, exist_ok=True)

    await hass.async_add_executor_job(mkdir)
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    return RoborockStorage(hass, store, map_path)


class RoborockStorage:
    def __init__(
        self, hass: HomeAssistant, store: Store[dict[str, Any]], map_path: setattr
    ) -> None:
        """Initialize NestEventMediaStore."""
        self._hass = hass
        self._store = store
        self._data: dict[str, Any] | None = None
        self._map_path = map_path

    async def async_load(self) -> dict | None:
        """Load data."""
        if self._data is None:
            self._devices = await self._get_devices()
            if (data := await self._store.async_load()) is None:
                _LOGGER.debug("Loaded empty event store")
                self._data = {}
            else:
                _LOGGER.debug("Loaded event store with %d records", len(data))
                self._data = data
        return self._data

    async def async_load_maps(self, media_key: str) -> bytes | None:
        """Load media content."""
        filename = self.get_media_filename(media_key)

        def load_media(filename: str) -> bytes | None:
            if not os.path.exists(filename):
                return None
            _LOGGER.debug("Reading event media from disk store: %s", filename)
            with open(filename, "rb") as media:
                return media.read()

        try:
            return await self._hass.async_add_executor_job(load_media, filename)
        except OSError as err:
            _LOGGER.error("Unable to read media file: %s %s", filename, err)
            return None

    async def async_save_maps(self, media_key: str, content: bytes) -> None:
        """Write media content."""
        filename = self.get_media_filename(media_key)

        def save_media(filename: str, content: bytes) -> None:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            if os.path.exists(filename):
                _LOGGER.debug(
                    "Event media already exists, not overwriting: %s", filename
                )
                return
            _LOGGER.debug("Saving event media to disk store: %s", filename)
            with open(filename, "wb") as media:
                media.write(content)

        try:
            await self._hass.async_add_executor_job(save_media, filename, content)
        except OSError as err:
            _LOGGER.error("Unable to write media file: %s %s", filename, err)

    async def async_remove_map(self, media_key: str) -> None:
        """Remove media content."""
        filename = self.get_media_filename(media_key)

        def remove_media(filename: str) -> None:
            if not os.path.exists(filename):
                return None
            _LOGGER.debug("Removing event media from disk store: %s", filename)
            os.remove(filename)

        try:
            await self._hass.async_add_executor_job(remove_media, filename)
        except OSError as err:
            _LOGGER.error("Unable to remove media file: %s %s", filename, err)
