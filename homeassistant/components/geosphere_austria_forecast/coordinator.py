"""Data update coordinator for the GeoSphere Austria Forecast integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from zamg import NwpClient, NwpForecast, ZamgApiError, ZamgNoDataError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_REQUESTS_PER_SECOND, REQUEST_SLOTS

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)
# A request keeps its slot this long after it ends, so that no more than
# MAX_REQUESTS_PER_SECOND requests start within a second.
SECONDS_PER_REQUEST_SLOT = 1

type GeoSphereAustriaForecastConfigEntry = ConfigEntry[
    GeoSphereAustriaForecastCoordinator
]


class GeoSphereAustriaForecastCoordinator(DataUpdateCoordinator[NwpForecast]):
    """Class to manage fetching the forecast for one location."""

    config_entry: GeoSphereAustriaForecastConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GeoSphereAustriaForecastConfigEntry,
        client: NwpClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.latitude: float = entry.data[CONF_LATITUDE]
        self.longitude: float = entry.data[CONF_LONGITUDE]
        # Shared by the entries of all locations, which share the API's limit.
        self._request_slots = hass.data.setdefault(
            REQUEST_SLOTS, asyncio.Semaphore(MAX_REQUESTS_PER_SECOND)
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GeoSphere Austria",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def _async_update_data(self) -> NwpForecast:
        """Fetch the forecast from GeoSphere Austria."""
        async with self._request_slots:
            try:
                return await self.client.get_forecast(
                    latitude=self.latitude, longitude=self.longitude
                )
            except ZamgApiError as err:
                raise UpdateFailed(
                    f"Error communicating with GeoSphere Austria: {err}",
                    retry_after=err.rate_limit_reset or None,
                ) from err
            except ZamgNoDataError as err:
                raise UpdateFailed(
                    f"Invalid data from GeoSphere Austria: {err}"
                ) from err
            finally:
                await asyncio.sleep(SECONDS_PER_REQUEST_SLOT)
