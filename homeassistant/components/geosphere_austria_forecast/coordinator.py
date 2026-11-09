"""Data update coordinator for the GeoSphere Austria Forecast integration."""

from datetime import timedelta
import logging
from typing import override

from zamg import NwpClient, NwpForecast, ZamgApiError, ZamgNoDataError

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)

type GeoSphereAustriaForecastConfigEntry = ConfigEntry[
    dict[str, GeoSphereAustriaForecastCoordinator]
]


class GeoSphereAustriaForecastCoordinator(DataUpdateCoordinator[NwpForecast]):
    """Class to manage fetching the forecast for one location."""

    config_entry: GeoSphereAustriaForecastConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GeoSphereAustriaForecastConfigEntry,
        subentry: ConfigSubentry,
        client: NwpClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {subentry.title}",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.latitude: float = subentry.data[CONF_LATITUDE]
        self.longitude: float = subentry.data[CONF_LONGITUDE]
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="GeoSphere Austria",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def _async_update_data(self) -> NwpForecast:
        """Fetch the forecast from GeoSphere Austria."""
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
            raise UpdateFailed(f"Invalid data from GeoSphere Austria: {err}") from err
