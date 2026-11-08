"""VRM Coordinator and Client."""

from dataclasses import dataclass
import datetime as dt
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
    """Daily forecast aggregations and the hourly watt-hours kept for the service."""

    site_id: int
    solar: ForecastAggregations | None
    consumption: ForecastAggregations | None
    solar_wh: dict[dt.datetime, float]
    consumption_wh: dict[dt.datetime, float]


def _forecast_aggregation(value: object) -> ForecastAggregations | None:
    """Return an aggregation, treating a missing or false series as absent."""
    if isinstance(value, ForecastAggregations):
        return value
    return None


def _as_watt_hours(value: object) -> float | None:
    """Ignore booleans and other non-numeric samples."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _hourly_watt_hours(
    aggregation: ForecastAggregations | None, time_zone: dt.tzinfo
) -> dict[dt.datetime, float]:
    """Return hourly watt-hours keyed by timezone-aware timestamps.

    ForecastAggregations.records stores unix seconds. The API sends milliseconds
    and the client converts them before building the aggregation.
    """
    if aggregation is None:
        return {}
    points: dict[dt.datetime, float] = {}
    for timestamp, value in aggregation.records:
        watt_hours = _as_watt_hours(value)
        if watt_hours is None:
            continue
        points[dt.datetime.fromtimestamp(timestamp, time_zone)] = watt_hours
    return dict(sorted(points.items()))


async def get_forecast(client: VictronVRMClient, site_id: int) -> VRMForecastStore:
    """Get the forecast data."""
    time_zone = dt_util.DEFAULT_TIME_ZONE
    now = dt_util.now(time_zone)
    today = now.date()
    start = int(
        dt.datetime.combine(
            today - dt.timedelta(days=1), dt.time.min, time_zone
        ).timestamp()
    )
    # Get timestamp of the end of 6th day from now
    end = int(
        dt.datetime.combine(
            today + dt.timedelta(days=6), dt.time.min, time_zone
        ).timestamp()
    )
    stats = await client.installations.stats(
        site_id,
        start=start,
        end=end,
        interval="hours",
        type="forecast",
        return_aggregations=True,
        time_zone=time_zone,
    )
    solar = _forecast_aggregation(stats.get("solar_yield"))
    consumption = _forecast_aggregation(stats.get("consumption"))
    # UTC keys stay distinct when a local hour is repeated.
    return VRMForecastStore(
        site_id=site_id,
        solar=solar,
        consumption=consumption,
        solar_wh=_hourly_watt_hours(solar, dt.UTC),
        consumption_wh=_hourly_watt_hours(consumption, dt.UTC),
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
            update_interval=dt.timedelta(minutes=60),
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
