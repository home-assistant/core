"""Coordinator for the Theben Conexa Smartmeter gateway integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_utc_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .smgw import ConexaSMGW

_LOGGER = logging.getLogger(__name__)


@dataclass
class ThebenRuntimeData:
    """Data for the Theben Conexa Smartmeter gateway integration."""

    api: ConexaSMGW
    coordinator: "SmgwSensorCoordinator"


type ThebenConfigEntry = ConfigEntry[ThebenRuntimeData]


class SmgwSensorCoordinator(DataUpdateCoordinator):
    """The data update coordinator for the Theben Conexa Smartmeter gateway integration."""

    def __init__(self, hass: HomeAssistant, entry: ThebenConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Theben Conexa Local Poll",
            config_entry=entry,
            # Set to None so HA doesn't poll on a standard rolling interval
            update_interval=None,
            always_update=False,
        )
        # Currently the SMGW provides new data only every 15 minutes at the starting of the hour (in UTC).
        # So we leverage this information to set up a scheduled poll at
        # exactly these times + some seconds to allow for processing.
        self._scheduled_updates = async_track_utc_time_change(
            hass,
            self._scheduled_update,
            minute=[0, 15, 30, 45],
            second=40,
        )
        self._unscheduled_updates: CALLBACK_TYPE | None = None
        self.retries = 0

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        # If data is None, this is the first refresh cycle
        is_first_update = self.data is None

        if self.config_entry is None or self.config_entry.runtime_data is None:
            raise ValueError("Runtime data is not set")

        _LOGGER.debug("Fetching data from API")
        vals = await self.config_entry.runtime_data.api.getLatestValues()

        now_utc = dt_util.utcnow()
        _LOGGER.debug("Data fetched at %s: %s", now_utc, vals)
        # On scheduled update the data should be fresh. Do a quick check to confirm.
        # If the smgw was busy and returned old data we try to reschedule in 60 seconds from now 2 times
        # before giving up and accepting the old data, to avoid spamming the smgw with requests.
        if not is_first_update:
            meter_timestamp: str = next(iter(vals.values())).utcTimestamp
            meter_datetime = dt_util.parse_datetime(meter_timestamp)
            if meter_datetime is None:
                raise ValueError(
                    f"Could not parse meter timestamp: {meter_timestamp!r}"
                )
            age = (now_utc - meter_datetime).total_seconds()
            _LOGGER.debug("Data age in seconds: %s", age)

            if age > 100 and self.retries < 2:
                _LOGGER.debug(
                    "Data is quite old (age: %s seconds). Likely because the SMGW was busy, retrying in 60 seconds",
                    age,
                )
                self._unscheduled_updates = async_track_point_in_utc_time(
                    self.hass,
                    self._unscheduled_update,
                    dt_util.utcnow() + timedelta(seconds=60),
                )
                self.retries += 1
            else:
                _LOGGER.debug(
                    "Giving up on retrying, next update will be according to schedule"
                )
                self.retries = 0

        return vals

    async def _scheduled_update(self, now: datetime) -> None:
        """Triggered exactly at the in __init__ specified time pattern."""
        _LOGGER.debug("Starting scheduled poll at %s", now)
        if self._unscheduled_updates:
            _LOGGER.debug(
                "Canceling pending unscheduled updates since we are doing a scheduled update now"
            )
            self._unscheduled_updates()
            self._unscheduled_updates = None
        await self.async_refresh()

    async def _unscheduled_update(self, now: datetime) -> None:
        """Triggered at a retry."""
        _LOGGER.debug("Starting out of schedule poll at %s", now)
        await self.async_refresh()
