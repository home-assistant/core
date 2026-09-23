"""VRM Coordinator and Client."""

from dataclasses import dataclass
import datetime
from typing import override

from victron_vrm import VictronVRMClient
from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.models.aggregations import ForecastAggregations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_SITE_ID, DOMAIN, LOGGER

type VictronRemoteMonitoringConfigEntry = ConfigEntry[
    VictronRemoteMonitoringDataUpdateCoordinator
]


@dataclass
class VRMForecastStore:
    """Class to hold the forecast data."""

    site_id: int
    solar: ForecastAggregations | None
    consumption: ForecastAggregations | None


@dataclass(kw_only=True)
class LocalForecastAggregations(ForecastAggregations):
    """Aggregate VRM forecast records using Home Assistant's local days."""

    time_zone: datetime.tzinfo

    @property
    def dt_now(self) -> datetime.datetime:
        """Return the current time in Home Assistant's time zone."""
        return super().dt_now.astimezone(self.time_zone)

    def _day_range(self, day_offset: int) -> tuple[int, int]:
        day = self.dt_now.date() + datetime.timedelta(days=day_offset)
        start = datetime.datetime.combine(day, datetime.time.min, self.time_zone)
        end = datetime.datetime.combine(
            day + datetime.timedelta(days=1), datetime.time.min, self.time_zone
        )
        return int(start.timestamp()), int(end.timestamp())

    @property
    def yesterday_range(self) -> tuple[int, int]:
        """Return the local yesterday range."""
        return self._day_range(-1)

    @property
    def today_range(self) -> tuple[int, int]:
        """Return the local today range."""
        return self._day_range(0)

    @property
    def tomorrow_range(self) -> tuple[int, int]:
        """Return the local tomorrow range."""
        return self._day_range(1)


def _local_aggregations(
    forecast: ForecastAggregations | None, time_zone: datetime.tzinfo
) -> LocalForecastAggregations | None:
    if forecast is None:
        return None
    return LocalForecastAggregations(
        start=forecast.start,
        end=forecast.end,
        site_id=forecast.site_id,
        records=forecast.records,
        custom_dt_now=forecast.custom_dt_now,
        time_zone=time_zone,
    )


async def get_forecast(client: VictronVRMClient, site_id: int) -> VRMForecastStore:
    """Get the forecast data."""
    time_zone = dt_util.DEFAULT_TIME_ZONE
    now = dt_util.now(time_zone)
    today = now.date()
    start = int(
        datetime.datetime.combine(
            today - datetime.timedelta(days=1), datetime.time.min, time_zone
        ).timestamp()
    )
    # Get timestamp of the end of 6th day from now
    end = int(
        datetime.datetime.combine(
            today + datetime.timedelta(days=6), datetime.time.min, time_zone
        ).timestamp()
    )
    stats = await client.installations.stats(
        site_id,
        start=start,
        end=end,
        interval="hours",
        type="forecast",
        return_aggregations=True,
    )
    return VRMForecastStore(
        solar=_local_aggregations(stats["solar_yield"], time_zone),
        consumption=_local_aggregations(stats["consumption"], time_zone),
        site_id=site_id,
    )


class VictronRemoteMonitoringDataUpdateCoordinator(
    DataUpdateCoordinator[VRMForecastStore]
):
    """Class to manage fetching VRM Forecast data."""

    config_entry: VictronRemoteMonitoringConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: VictronRemoteMonitoringConfigEntry,
    ) -> None:
        """Initialize."""
        self.client = VictronVRMClient(
            token=config_entry.data[CONF_API_TOKEN],
            client_session=async_get_clientsession(hass),
        )
        self.site_id = config_entry.data[CONF_SITE_ID]
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=datetime.timedelta(minutes=60),
        )

    @override
    async def _async_update_data(self) -> VRMForecastStore:
        """Fetch data from VRM API."""
        try:
            return await get_forecast(self.client, self.site_id)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Invalid authentication for VRM API: {err}"
            ) from err
        except VictronVRMError as err:
            raise UpdateFailed(f"Cannot connect to VRM API: {err}") from err
