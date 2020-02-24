"""Lovelace dashboard support."""
from abc import ABC, abstractmethod
import os
import time

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import storage
from homeassistant.util.yaml import load_yaml

from .const import (
    DOMAIN,
    EVENT_LOVELACE_UPDATED,
    MODE_STORAGE,
    MODE_YAML,
    ConfigNotFound,
)

CONFIG_STORAGE_KEY_DEFAULT = DOMAIN
CONFIG_STORAGE_VERSION = 1


class LovelaceConfig(ABC):
    """Base class for Lovelace config."""

    def __init__(self, hass, url_path):
        """Initialize Lovelace config."""
        self.hass = hass
        self.url_path = url_path

    @property
    @abstractmethod
    def mode(self) -> str:
        """Return mode of the lovelace config."""

    @abstractmethod
    async def async_get_info(self):
        """Return the config info."""

    @abstractmethod
    async def async_load(self, force):
        """Load config."""

    async def async_save(self, config):
        """Save config."""
        raise HomeAssistantError("Not supported")

    async def async_delete(self):
        """Delete config."""
        raise HomeAssistantError("Not supported")

    @callback
    def _config_updated(self):
        """Fire config updated event."""
        self.hass.bus.async_fire(EVENT_LOVELACE_UPDATED, {"url_path": self.url_path})


class LovelaceStorage(LovelaceConfig):
    """Class to handle Storage based Lovelace config."""

    def __init__(self, hass, url_path):
        """Initialize Lovelace config based on storage helper."""
        super().__init__(hass, url_path)
        if url_path is None:
            storage_key = CONFIG_STORAGE_KEY_DEFAULT
        else:
            raise ValueError("Storage-based dashboards are not supported")

        self._store = storage.Store(hass, CONFIG_STORAGE_VERSION, storage_key)
        self._data = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return MODE_STORAGE

    async def async_get_info(self):
        """Return the YAML storage mode."""
        if self._data is None:
            await self._load()

        if self._data["config"] is None:
            return {"mode": "auto-gen"}

        return _config_info(self.mode, self._data["config"])

    async def async_load(self, force):
        """Load config."""
        if self.hass.config.safe_mode:
            raise ConfigNotFound

        if self._data is None:
            await self._load()

        config = self._data["config"]

        if config is None:
            raise ConfigNotFound

        return config

    async def async_save(self, config):
        """Save config."""
        if self._data is None:
            await self._load()
        self._data["config"] = config
        self._config_updated()
        await self._store.async_save(self._data)

    async def async_delete(self):
        """Delete config."""
        await self.async_save(None)

    async def _load(self):
        """Load the config."""
        data = await self._store.async_load()
        self._data = data if data else {"config": None}


class LovelaceYAML(LovelaceConfig):
    """Class to handle YAML-based Lovelace config."""

    def __init__(self, hass, url_path, path):
        """Initialize the YAML config."""
        super().__init__(hass, url_path)
        self.path = hass.config.path(path)
        self._cache = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return MODE_YAML

    async def async_get_info(self):
        """Return the YAML storage mode."""
        try:
            config = await self.async_load(False)
        except ConfigNotFound:
            return {
                "mode": self.mode,
                "error": "{} not found".format(self.path),
            }

        return _config_info(self.mode, config)

    async def async_load(self, force):
        """Load config."""
        is_updated, config = await self.hass.async_add_executor_job(
            self._load_config, force
        )
        if is_updated:
            self._config_updated()
        return config

    def _load_config(self, force):
        """Load the actual config."""
        # Check for a cached version of the config
        if not force and self._cache is not None:
            config, last_update = self._cache
            modtime = os.path.getmtime(self.path)
            if config and last_update > modtime:
                return False, config

        is_updated = self._cache is not None

        try:
            config = load_yaml(self.path)
        except FileNotFoundError:
            raise ConfigNotFound from None

        self._cache = (config, time.time())
        return is_updated, config


def _config_info(mode, config):
    """Generate info about the config."""
    return {
        "mode": mode,
        "resources": len(config.get("resources", [])),
        "views": len(config.get("views", [])),
    }
