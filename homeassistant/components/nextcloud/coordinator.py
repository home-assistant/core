"""Data update coordinator for the Nextcloud integration."""

import logging
from typing import Any

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type NextcloudConfigEntry = ConfigEntry[NextcloudDataUpdateCoordinator]


class NextcloudDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Nextcloud data update coordinator."""

    config_entry: NextcloudConfigEntry

    def __init__(
        self, hass: HomeAssistant, ncm: NextcloudMonitor, entry: NextcloudConfigEntry
    ) -> None:
        """Initialize the Nextcloud coordinator."""
        self.ncm = ncm
        self.url = entry.data[CONF_URL]

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=self.url,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    # Use recursion to create list of sensors & values based on nextcloud api data
    def _get_data_points(
        self, api_data: dict, key_path: str = "", leaf: bool = False
    ) -> dict[str, Any]:
        """Use Recursion to discover data-points and values.

        Get dictionary of data-points by recursing through dict returned by api until
        the dictionary value does not contain another dictionary and use the
        resulting path of dictionary keys and resulting value as the name/value
        for the data-point.

        returns: dictionary of data-point/values
        """
        result = {}
        for key, value in api_data.items():
            if isinstance(value, dict):
                if leaf:
                    key_path = f"{key}_"
                if not leaf:
                    key_path += f"{key}_"
                leaf = True
                result.update(self._get_data_points(value, key_path, leaf))
            elif key == "cpuload" and isinstance(value, list):
                result[f"{key_path}{key}_1"] = value[0]
                result[f"{key_path}{key}_5"] = value[1]
                result[f"{key_path}{key}_15"] = value[2]
                leaf = False
            else:
                result[f"{key_path}{key}"] = value
                leaf = False
        return result

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all Nextcloud data."""

        def _update_data() -> None:
            try:
                self.ncm.update()
            except NextcloudMonitorError as ex:
                raise UpdateFailed from ex

        await self.hass.async_add_executor_job(_update_data)
        return self._get_data_points(self.ncm.data)
