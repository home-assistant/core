"""DataUpdateCoordinator for the Ambient Weather Network integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from aioambient import OpenAPI
from aioambient.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_LAST_DATA, DOMAIN, LOGGER, SCAN_INTERVAL


class AmbientNetworkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Ambient Network Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: OpenAPI) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api
        self.data = {}
        self.outstanding_errors: list[str] = []

    def _report_error(self, message: str) -> None:
        """Report an error by logging it. Only log the first occurrence of each error."""

        if message not in self.outstanding_errors:
            LOGGER.warning(message)
            self.outstanding_errors.append(message)

    def _clear_errors(self) -> None:
        """Clear all outstanding errors."""

        if self.outstanding_errors:
            LOGGER.info(f"Station '{self.config_entry.title}' is back online")
            self.outstanding_errors = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the Ambient Network."""

        try:
            response = await self.api.get_device_details(
                self.config_entry.data[CONF_MAC]
            )
        except RequestError:
            self._report_error("Cannot connect to Ambient Network")
            return {}

        if (last_data := response.get(API_LAST_DATA)) is None:
            # Use previous data
            self._report_error(
                f"Station '{self.config_entry.title}' did not report any data"
            )
            last_data = self.data

        # Eliminate data if the station hasn't been updated for a while.
        if (created_at := last_data.get("created_at")) is None:
            self._report_error(
                f"Station '{self.config_entry.title}' did not report a time stamp"
            )
            return {}

        # Eliminate data that has been generated more than an hour ago. The station is
        # probably offline.
        if int(created_at / 1000) < int(
            (datetime.now() - timedelta(hours=1)).timestamp()
        ):
            self._report_error(
                f"Station '{self.config_entry.title}' reported stale data"
            )
            return {}

        self._clear_errors()
        return cast(dict[str, Any], last_data)
