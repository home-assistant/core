"""DataUpdateCoordinator for the Ambient Weather Network integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from aioambient import OpenAPI
from aioambient.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import API_LAST_DATA, DOMAIN, LOGGER
from .helper import get_station_name

SCAN_INTERVAL = timedelta(minutes=5)

type AmbientNetworkConfigEntry = ConfigEntry[AmbientNetworkDataUpdateCoordinator]


class AmbientNetworkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Ambient Network Data Update Coordinator."""

    config_entry: AmbientNetworkConfigEntry
    station_name: str
    last_measured: datetime | None = None

    def __init__(
        self, hass: HomeAssistant, config_entry: AmbientNetworkConfigEntry, api: OpenAPI
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the Ambient Network."""

        try:
            response = await self.api.get_device_details(
                self.config_entry.data[CONF_MAC]
            )
        except RequestError as ex:
            raise UpdateFailed("Cannot connect to Ambient Network") from ex

        self.station_name = get_station_name(response)

        if (last_data := response.get(API_LAST_DATA)) is None:
            raise UpdateFailed(
                f"Station '{self.config_entry.title}' did not report any data"
            )

        # Some stations do not report a "created_at" or "dateutc".
        # See https://github.com/home-assistant/core/issues/116917
        if (ts := last_data.get("created_at")) is not None or (
            ts := last_data.get("dateutc")
        ) is not None:
            self.last_measured = datetime.fromtimestamp(
                ts / 1000, tz=dt_util.DEFAULT_TIME_ZONE
            )

        return cast(dict[str, Any], last_data)
