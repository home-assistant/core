"""Store RTM configuration in Home Assistant storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LOGGER

LEGACY_CONFIG_FILE_NAME = ".remember_the_milk.conf"
STORE_DELAY_SAVE = 30


class StoredUserConfig(TypedDict, total=False):
    """Represent the stored config for a username."""

    id_map: dict[str, TaskIds]
    token: str


class TaskIds(TypedDict):
    """Represent the stored ids of a task."""

    list_id: str
    timeseries_id: str
    task_id: str


class RememberTheMilkConfiguration:
    """Internal configuration data for Remember The Milk."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create new instance of configuration."""
        self._legacy_config_path = hass.config.path(LEGACY_CONFIG_FILE_NAME)
        self._config: dict[str, StoredUserConfig] = {}
        self._hass = hass
        self._store = Store[dict[str, StoredUserConfig]](hass, 1, DOMAIN)

    async def setup(self) -> None:
        """Set up the configuration."""
        if not (config := await self._hass.async_add_executor_job(self._load_legacy)):
            config = await self._load()

        self._config = config or {}

    def _load_legacy(self) -> dict[str, StoredUserConfig] | None:
        """Load configuration from legacy storage."""
        # Do not load from legacy if the new store exists.
        if Path(self._store.path).exists():
            return None

        LOGGER.debug(
            "Loading legacy configuration from file: %s", self._legacy_config_path
        )
        config: dict[str, StoredUserConfig] | None = None

        try:
            config = json.loads(
                Path(self._legacy_config_path).read_text(encoding="utf8")
            )
        except FileNotFoundError:
            LOGGER.debug(
                "Missing legacy configuration file: %s", self._legacy_config_path
            )
        except OSError:
            LOGGER.debug(
                "Failed to read from legacy configuration file, %s, using empty configuration",
                self._legacy_config_path,
            )
        except ValueError:
            LOGGER.error(
                "Failed to parse legacy configuration file, %s, using empty configuration",
                self._legacy_config_path,
            )

        return config

    async def _load(self) -> dict[str, StoredUserConfig] | None:
        """Load the store."""
        return await self._store.async_load()

    @callback
    def _save_config(self) -> None:
        """Save config."""
        self._store.async_delay_save(self._data_to_save, STORE_DELAY_SAVE)

    @callback
    def _data_to_save(self) -> dict[str, StoredUserConfig]:
        """Return data to save."""
        return self._config

    def get_token(self, profile_name: str) -> str | None:
        """Get the server token for a profile."""
        if profile_name in self._config:
            return self._config[profile_name][CONF_TOKEN]
        return None

    @callback
    def set_token(self, profile_name: str, token: str) -> None:
        """Store a new server token for a profile."""
        self._initialize_profile(profile_name)
        self._config[profile_name][CONF_TOKEN] = token
        self._save_config()

    @callback
    def delete_token(self, profile_name: str) -> None:
        """Delete a token for a profile.

        Usually called when the token has expired.
        """
        self._config.pop(profile_name, None)
        self._save_config()

    def _initialize_profile(self, profile_name: str) -> None:
        """Initialize the data structures for a profile."""
        if profile_name not in self._config:
            self._config[profile_name] = {}
        if "id_map" not in self._config[profile_name]:
            self._config[profile_name]["id_map"] = {}

    def get_rtm_id(
        self, profile_name: str, hass_id: str
    ) -> tuple[str, str, str] | None:
        """Get the RTM ids for a Home Assistant task ID.

        The id of a RTM tasks consists of the tuple:
        list id, timeseries id and the task id.
        """
        self._initialize_profile(profile_name)
        task_ids = self._config[profile_name]["id_map"].get(hass_id)
        if task_ids is None:
            return None
        return task_ids["list_id"], task_ids["timeseries_id"], task_ids["task_id"]

    @callback
    def set_rtm_id(
        self,
        profile_name: str,
        hass_id: str,
        list_id: str,
        time_series_id: str,
        rtm_task_id: str,
    ) -> None:
        """Add/Update the RTM task ID for a Home Assistant task ID."""
        self._initialize_profile(profile_name)
        ids = TaskIds(
            list_id=list_id,
            timeseries_id=time_series_id,
            task_id=rtm_task_id,
        )
        self._config[profile_name]["id_map"][hass_id] = ids
        self._save_config()

    @callback
    def delete_rtm_id(self, profile_name: str, hass_id: str) -> None:
        """Delete a key mapping."""
        self._initialize_profile(profile_name)
        if hass_id in self._config[profile_name]["id_map"]:
            del self._config[profile_name]["id_map"][hass_id]
            self._save_config()
