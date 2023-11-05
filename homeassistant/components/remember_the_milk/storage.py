"""Provide storage for Remember The Milk integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import LOGGER

CONFIG_FILE_NAME = ".remember_the_milk.conf"
CONF_ID_MAP = "id_map"
CONF_LIST_ID = "list_id"
CONF_TASK_ID = "task_id"
CONF_TIMESERIES_ID = "timeseries_id"


class RememberTheMilkConfiguration:
    """Internal configuration data for Remember The Milk."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create new instance of configuration."""
        self._config_file_path = hass.config.path(CONFIG_FILE_NAME)
        self._config: dict[str, Any] = {}

    def setup(self) -> None:
        """Set up the configuration."""
        LOGGER.debug("Loading configuration from file: %s", self._config_file_path)
        try:
            self._config = json.loads(
                Path(self._config_file_path).read_text(encoding="utf8")
            )
        except FileNotFoundError:
            LOGGER.debug("Missing configuration file: %s", self._config_file_path)
        except OSError:
            LOGGER.debug(
                "Failed to read from configuration file, %s, using empty configuration",
                self._config_file_path,
            )
        except ValueError:
            LOGGER.error(
                "Failed to parse configuration file, %s, using empty configuration",
                self._config_file_path,
            )

    def _save_config(self) -> None:
        """Write the configuration to a file."""
        Path(self._config_file_path).write_text(
            json.dumps(self._config), encoding="utf8"
        )

    def _initialize_profile(self, profile_name: str) -> None:
        """Initialize the data structures for a profile."""
        if profile_name not in self._config:
            self._config[profile_name] = {}
        if CONF_ID_MAP not in self._config[profile_name]:
            self._config[profile_name][CONF_ID_MAP] = {}

    def get_rtm_id(
        self, profile_name: str, hass_id: str
    ) -> tuple[int, int, int] | None:
        """Get the RTM ids for a Home Assistant task ID.

        The id of a RTM tasks consists of the tuple:
        list id, timeseries id and the task id.
        """
        self._initialize_profile(profile_name)
        ids = self._config[profile_name][CONF_ID_MAP].get(hass_id)
        if ids is None:
            return None
        return ids[CONF_LIST_ID], ids[CONF_TIMESERIES_ID], ids[CONF_TASK_ID]

    def set_rtm_id(
        self,
        profile_name: str,
        hass_id: str,
        list_id: int,
        time_series_id: int,
        rtm_task_id: int,
    ) -> None:
        """Add/Update the RTM task ID for a Home Assistant task ID."""
        self._initialize_profile(profile_name)
        id_tuple = {
            CONF_LIST_ID: list_id,
            CONF_TIMESERIES_ID: time_series_id,
            CONF_TASK_ID: rtm_task_id,
        }
        self._config[profile_name][CONF_ID_MAP][hass_id] = id_tuple
        self._save_config()

    def delete_rtm_id(self, profile_name: str, hass_id: str) -> None:
        """Delete a key mapping."""
        self._initialize_profile(profile_name)
        if hass_id in self._config[profile_name][CONF_ID_MAP]:
            del self._config[profile_name][CONF_ID_MAP][hass_id]
            self._save_config()
