"""VRM Solar Forecast Coordinator and Client."""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import re

from victron_vrm import VictronVRMClient
from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.utils import dt_now, is_dt_timezone_aware

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_API_KEY, CONF_SITE_ID, DOMAIN, LOGGER

type VRMForecastsConfigEntry = ConfigEntry[VRMForecastsDataUpdateCoordinator]


jwt_regex = re.compile(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$")


@dataclass
class ForecastEstimates:
    """Class to hold and calculate forecast estimates."""

    start: int
    end: int
    site_id: int
    records: list[tuple[int, float]]
    custom_dt_now: Callable | None = None

    def __post_init__(self) -> None:
        """Post-initialize the ForecastEstimates class."""
        if self.start != min(x[0] for x in self.records):
            LOGGER.warning(f"Start time {self.start} does not match records start time")
            self.start = min(x[0] for x in self.records)
        if self.end != max(x[0] for x in self.records):
            LOGGER.warning(f"End time {self.end} does not match records end time")
            self.end = max(x[0] for x in self.records)
        LOGGER.warning(f"POST_INIT dt_now: {self.dt_now.isoformat()}")

    @property
    def dt_now(self) -> datetime.datetime:
        """Get the current datetime."""
        if self.custom_dt_now is not None:
            dt = self.custom_dt_now()
            if not is_dt_timezone_aware(dt):
                raise ValueError("custom_dt_now must return a timezone-aware datetime")
            LOGGER.warning(f"Using custom dt_now: {dt.isoformat()}")
            return dt
        LOGGER.warning("Using default dt_now")
        return datetime.datetime.now(tz=datetime.UTC)

    @property
    def start_date(self) -> datetime.datetime:
        """Get the start date."""
        return datetime.datetime.fromtimestamp(self.start, tz=datetime.UTC)

    @property
    def end_date(self) -> datetime.datetime:
        """Get the end date."""
        return datetime.datetime.fromtimestamp(self.end, tz=datetime.UTC)

    @property
    def get_dict_isoformat(self) -> dict[str, float]:
        """Get the dictionary with ISO formatted timestamps."""
        return {
            datetime.datetime.fromtimestamp(x, tz=datetime.UTC).isoformat(): y
            for x, y in self.records
        }

    @property
    def yesterday_range(self) -> tuple[int, int]:
        """Get the range of yesterday."""
        end = self.start + (3600 * 24)
        return self.start, end

    @property
    def today_range(self) -> tuple[int, int]:
        """Get the range of today."""
        start = self.start + (3600 * 24)
        end = start + (3600 * 24)
        return start, end

    @property
    def tomorrow_range(self) -> tuple[int, int]:
        """Get the range of tomorrow."""
        start = self.start + (3600 * 48)
        end = start + (3600 * 24)
        return start, end

    @property
    def next_48_hours_range(self) -> tuple[int, int]:
        """Get the range of the next 48 hours."""
        start = int(self.dt_now.replace(minute=0, second=0, microsecond=0).timestamp())
        end = start + (3600 * 48)
        return start, end

    @property
    def next_hour_timestamp(self) -> tuple[int, int]:
        """Get the range of the next hour."""
        start = int(
            (
                self.dt_now.replace(minute=0, second=0, microsecond=0)
                + datetime.timedelta(hours=1)
            ).timestamp()
        )
        end = start + 3600
        return start, end

    @property
    def current_hour_timestamp(self) -> tuple[int, int]:
        """Get the range of the current hour."""
        start = int(self.dt_now.replace(minute=0, second=0, microsecond=0).timestamp())
        end = start + 3600
        return start, end

    @property
    def today_left_range(self) -> tuple[int, int]:
        """Get the range of today left."""
        start = int(self.dt_now.timestamp())
        end = int(
            (
                self.dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
                + datetime.timedelta(days=1)
            ).timestamp()
        )
        return start, end

    @property
    def yesterday_total(self) -> float:
        """Get the total solar yield for yesterday."""
        return sum(
            y
            for x, y in self.records
            if self.yesterday_range[0] <= x < self.yesterday_range[1]
        )

    @property
    def yesterday_by_hour(self) -> dict[datetime.datetime, float]:
        """Get the solar yield for yesterday by hour."""
        return {
            datetime.datetime.fromtimestamp(x, tz=datetime.UTC): y
            for x, y in self.records
            if self.yesterday_range[0] <= x < self.yesterday_range[1]
        }

    @property
    def yesterday_peak_time(self) -> datetime.datetime:
        """Get the peak time for yesterday."""
        return sorted(
            [
                (datetime.datetime.fromtimestamp(x, tz=datetime.UTC), y)
                for x, y in self.records
                if self.yesterday_range[0] <= x < self.yesterday_range[1]
            ],
            key=lambda x: x[1],
            reverse=True,
        )[0][0]

    @property
    def today_total(self) -> float:
        """Get the total solar yield for today."""
        return sum(
            y for x, y in self.records if self.today_range[0] <= x < self.today_range[1]
        )

    @property
    def today_by_hour(self) -> dict[datetime.datetime, float]:
        """Get the solar yield for today by hour."""
        return {
            datetime.datetime.fromtimestamp(x, tz=datetime.UTC): y
            for x, y in self.records
            if self.today_range[0] <= x < self.today_range[1]
        }

    @property
    def today_peak_time(self) -> datetime.datetime:
        """Get the peak time for today."""
        return sorted(
            [
                (datetime.datetime.fromtimestamp(x, tz=datetime.UTC), y)
                for x, y in self.records
                if self.today_range[0] <= x < self.today_range[1]
            ],
            key=lambda x: x[1],
            reverse=True,
        )[0][0]

    @property
    def today_left_total(self) -> float:
        """Get the total solar yield for today left."""
        return sum(
            y
            for x, y in self.records
            if self.today_left_range[0] <= x < self.today_left_range[1]
        )

    @property
    def tomorrow_total(self) -> float:
        """Get the total solar yield for tomorrow."""
        return sum(
            y
            for x, y in self.records
            if self.tomorrow_range[0] <= x < self.tomorrow_range[1]
        )

    @property
    def tomorrow_by_hour(self) -> dict[datetime.datetime, float]:
        """Get the solar yield for tomorrow by hour."""
        return {
            datetime.datetime.fromtimestamp(x, tz=datetime.UTC): y
            for x, y in self.records
            if self.tomorrow_range[0] <= x < self.tomorrow_range[1]
        }

    @property
    def tomorrow_peak_time(self) -> datetime.datetime:
        """Get the peak time for tomorrow."""
        return sorted(
            [
                (datetime.datetime.fromtimestamp(x, tz=datetime.UTC), y)
                for x, y in self.records
                if self.tomorrow_range[0] <= x < self.tomorrow_range[1]
            ],
            key=lambda x: x[1],
            reverse=True,
        )[0][0]

    @property
    def current_hour_total(self) -> float:
        """Get the total solar yield for the current hour."""
        return sum(
            y
            for x, y in self.records
            if self.current_hour_timestamp[0] <= x < self.current_hour_timestamp[1]
        )

    @property
    def next_hour_total(self) -> float:
        """Get the total solar yield for the next hour."""
        return sum(
            y
            for x, y in self.records
            if self.next_hour_timestamp[0] <= x < self.next_hour_timestamp[1]
        )


@dataclass
class VRMForecastStore:
    """Class to hold the forecast data."""

    solar: ForecastEstimates
    consumption: ForecastEstimates
    site_id: int


async def get_forecast(client: VictronVRMClient, site_id: int) -> VRMForecastStore:
    """Get the forecast data."""
    start = int(
        (
            dt_now().replace(hour=0, minute=0, second=0, microsecond=0)
            - datetime.timedelta(days=1)
        ).timestamp()
    )
    # Get timestamp of the end of 6th day from now
    end = int(
        (
            dt_now().replace(hour=0, minute=0, second=0, microsecond=0)
            + datetime.timedelta(days=6)
        ).timestamp()
    )
    stats = await client.installations.stats(
        site_id, start=start, end=end, interval="hours", type="forecast"
    )
    consumption_forecast = ForecastEstimates(
        start=start,
        end=end,
        site_id=site_id,
        records=[(int(x / 1000), y) for x, y in stats["records"]["vrm_consumption_fc"]],
    )
    solar_forecast = ForecastEstimates(
        start=start,
        end=end,
        site_id=site_id,
        records=[
            (int(x / 1000), y) for x, y in stats["records"]["solar_yield_forecast"]
        ],
    )
    return VRMForecastStore(
        solar=solar_forecast,
        consumption=consumption_forecast,
        site_id=site_id,
    )


class VRMForecastsDataUpdateCoordinator(DataUpdateCoordinator[VRMForecastStore]):
    """Class to manage fetching VRM Forecast data."""

    config_entry: VRMForecastsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: VRMForecastsConfigEntry,
    ) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self.client = VictronVRMClient(
            token=config_entry.data[CONF_API_KEY],
            token_type="Bearer"
            if jwt_regex.match(config_entry.data[CONF_API_KEY])
            else "Token",
            client_session=get_async_client(hass),
        )
        self.site_id = config_entry.data[CONF_SITE_ID]
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=datetime.timedelta(minutes=60),
        )

    async def _async_update_data(
        self,
    ) -> VRMForecastStore:
        """Fetch data from VRM Forecast API."""
        try:
            return await get_forecast(self.client, self.site_id)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Invalid authentication for VRM API: {err}"
            ) from err
        except VictronVRMError as err:
            raise UpdateFailed(f"Cannot connect to VRM API: {err}") from err
