"""Lovelace dashboard support."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, storage
from homeassistant.helpers.json import json_bytes, json_fragment
from homeassistant.util.yaml import Secrets, load_yaml_dict

from .const import (
    CONF_ALLOW_SINGLE_WORD,
    CONF_ICON,
    CONF_URL_PATH,
    DOMAIN,
    EVENT_LOVELACE_UPDATED,
    LOVELACE_CONFIG_FILE,
    LOVELACE_DATA,
    MODE_STORAGE,
    MODE_YAML,
    STORAGE_DASHBOARD_CREATE_FIELDS,
    STORAGE_DASHBOARD_UPDATE_FIELDS,
    ConfigNotFound,
)

CONFIG_STORAGE_KEY_DEFAULT = DOMAIN
CONFIG_STORAGE_KEY = "lovelace.{}"
CONFIG_STORAGE_VERSION = 1
DASHBOARDS_STORAGE_KEY = f"{DOMAIN}_dashboards"
DASHBOARDS_STORAGE_VERSION = 1
_LOGGER = logging.getLogger(__name__)


class LovelaceConfig(ABC):
    """Base class for Lovelace config."""

    def __init__(
        self, hass: HomeAssistant, url_path: str | None, config: dict[str, Any] | None
    ) -> None:
        """Initialize Lovelace config."""
        self.hass = hass
        if config:
            self.config: dict[str, Any] | None = {**config, CONF_URL_PATH: url_path}
        else:
            self.config = None

    @property
    def url_path(self) -> str | None:
        """Return url path."""
        return self.config[CONF_URL_PATH] if self.config else None

    @property
    @abstractmethod
    def mode(self) -> str:
        """Return mode of the lovelace config."""

    @abstractmethod
    async def async_get_info(self) -> dict[str, Any]:
        """Return the config info."""

    @abstractmethod
    async def async_load(self, force: bool) -> dict[str, Any]:
        """Load config."""

    async def async_save(self, config: dict[str, Any]) -> None:
        """Save config."""
        raise HomeAssistantError("Not supported")

    async def async_delete(self) -> None:
        """Delete config."""
        raise HomeAssistantError("Not supported")

    @abstractmethod
    async def async_json(self, force: bool) -> json_fragment:
        """Return JSON representation of the config."""

    @callback
    def _config_updated(self) -> None:
        """Fire config updated event."""
        self.hass.bus.async_fire(EVENT_LOVELACE_UPDATED, {"url_path": self.url_path})


class LovelaceStorage(LovelaceConfig):
    """Class to handle Storage based Lovelace config."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any] | None) -> None:
        """Initialize Lovelace config based on storage helper."""
        if config is None:
            url_path: str | None = None
            storage_key = CONFIG_STORAGE_KEY_DEFAULT
        else:
            url_path = config[CONF_URL_PATH]
            storage_key = CONFIG_STORAGE_KEY.format(config["id"])

        super().__init__(hass, url_path, config)

        self._store = storage.Store[dict[str, Any]](
            hass, CONFIG_STORAGE_VERSION, storage_key
        )
        self._data: dict[str, Any] | None = None
        self._json_config: json_fragment | None = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return MODE_STORAGE

    async def async_get_info(self) -> dict[str, Any]:
        """Return the Lovelace storage info."""
        data = self._data or await self._load()
        if data["config"] is None:
            return {"mode": "auto-gen"}
        return _config_info(self.mode, data["config"])

    async def async_load(self, force: bool) -> dict[str, Any]:
        """Load config."""
        if self.hass.config.recovery_mode:
            raise ConfigNotFound

        data = self._data or await self._load()
        if (config := data["config"]) is None:
            raise ConfigNotFound

        return config  # type: ignore[no-any-return]

    async def async_json(self, force: bool) -> json_fragment:
        """Return JSON representation of the config."""
        if self.hass.config.recovery_mode:
            raise ConfigNotFound
        if self._data is None:
            await self._load()
        return self._json_config or self._async_build_json()

    async def async_save(self, config: dict[str, Any]) -> None:
        """Save config."""
        if self.hass.config.recovery_mode:
            raise HomeAssistantError("Saving not supported in recovery mode")

        if self._data is None:
            await self._load()
            if TYPE_CHECKING:
                assert self._data is not None
        self._data["config"] = config
        self._json_config = None
        self._config_updated()
        await self._store.async_save(self._data)

    async def async_delete(self) -> None:
        """Delete config."""
        if self.hass.config.recovery_mode:
            raise HomeAssistantError("Deleting not supported in recovery mode")

        await self._store.async_remove()
        self._data = None
        self._json_config = None
        self._config_updated()

    async def _load(self) -> dict[str, Any]:
        """Load the config."""
        data = await self._store.async_load()
        self._data = data if data else {"config": None}
        return self._data

    @callback
    def _async_build_json(self) -> json_fragment:
        """Build JSON representation of the config."""
        if self._data is None or self._data["config"] is None:
            raise ConfigNotFound
        self._json_config = json_fragment(json_bytes(self._data["config"]))
        return self._json_config


class LovelaceYAML(LovelaceConfig):
    """Class to handle YAML-based Lovelace config."""

    def __init__(
        self, hass: HomeAssistant, url_path: str | None, config: dict[str, Any] | None
    ) -> None:
        """Initialize the YAML config."""
        super().__init__(hass, url_path, config)

        self.path = hass.config.path(
            config[CONF_FILENAME] if config else LOVELACE_CONFIG_FILE
        )
        self._cache: tuple[dict[str, Any], float, json_fragment] | None = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return MODE_YAML

    async def async_get_info(self) -> dict[str, Any]:
        """Return the YAML storage mode."""
        try:
            config = await self.async_load(False)
        except ConfigNotFound:
            return {
                "mode": self.mode,
                "error": f"{self.path} not found",
            }

        return _config_info(self.mode, config)

    async def async_load(self, force: bool) -> dict[str, Any]:
        """Load config."""
        config, json = await self._async_load_or_cached(force)
        return config

    async def async_json(self, force: bool) -> json_fragment:
        """Return JSON representation of the config."""
        config, json = await self._async_load_or_cached(force)
        return json

    async def _async_load_or_cached(
        self, force: bool
    ) -> tuple[dict[str, Any], json_fragment]:
        """Load the config or return a cached version."""
        is_updated, config, json = await self.hass.async_add_executor_job(
            self._load_config, force
        )
        if is_updated:
            self._config_updated()
        return config, json

    def _load_config(self, force: bool) -> tuple[bool, dict[str, Any], json_fragment]:
        """Load the actual config."""
        # Check for a cached version of the config
        if not force and self._cache is not None:
            config, last_update, json = self._cache
            modtime = os.path.getmtime(self.path)
            if config and last_update > modtime:
                return False, config, json

        is_updated = self._cache is not None

        try:
            config = load_yaml_dict(
                self.path, Secrets(Path(self.hass.config.config_dir))
            )
        except FileNotFoundError:
            raise ConfigNotFound from None

        json = json_fragment(json_bytes(config))
        self._cache = (config, time.time(), json)
        return is_updated, config, json


def _config_info(mode: str, config: dict[str, Any]) -> dict[str, Any]:
    """Generate info about the config."""
    return {
        "mode": mode,
        "views": len(config.get("views", [])),
    }


class DashboardsCollection(collection.DictStorageCollection):
    """Collection of dashboards."""

    CREATE_SCHEMA = vol.Schema(STORAGE_DASHBOARD_CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(STORAGE_DASHBOARD_UPDATE_FIELDS)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dashboards collection."""
        super().__init__(
            storage.Store(hass, DASHBOARDS_STORAGE_VERSION, DASHBOARDS_STORAGE_KEY),
        )

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        url_path = data[CONF_URL_PATH]

        allow_single_word = data.pop(CONF_ALLOW_SINGLE_WORD, False)

        if not allow_single_word and "-" not in url_path:
            raise vol.Invalid("Url path needs to contain a hyphen (-)")

        if url_path in self.hass.data[DATA_PANELS]:
            raise vol.Invalid("Panel url path needs to be unique")

        return self.CREATE_SCHEMA(data)  # type: ignore[no-any-return]

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_URL_PATH]  # type: ignore[no-any-return]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        updated = {**item, **update_data}

        if CONF_ICON in updated and updated[CONF_ICON] is None:
            updated.pop(CONF_ICON)

        return updated


class DashboardsCollectionWebSocket(collection.DictStorageCollectionWebsocket):
    """Class to expose storage collection management over websocket."""

    @callback
    def ws_list_item(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Send Lovelace UI resources over WebSocket connection."""
        connection.send_result(
            msg["id"],
            [
                dashboard.config
                for dashboard in hass.data[LOVELACE_DATA].dashboards.values()
                if dashboard.config
            ],
        )
