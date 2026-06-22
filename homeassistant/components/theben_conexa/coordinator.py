"""Coordinator for the Theben Conexa Smartmeter gateway integration."""

from datetime import datetime, timedelta
import logging

from theben_conexa_smgw import ConexaSMGW

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_utc_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import MAX_MEASUREMENT_AGE, MAX_RETRIES

_LOGGER = logging.getLogger(__name__)

type ThebenConfigEntry = ConfigEntry[SmgwSensorCoordinator]


class SmgwSensorCoordinator(DataUpdateCoordinator[dict[str, ConexaSMGW.MeterValue]]):
    """The data update coordinator for the Theben Conexa Smartmeter gateway integration."""

    _api: ConexaSMGW
    gateway_info: ConexaSMGW.GatewayInfo

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
        self._scheduled_updates: CALLBACK_TYPE | None = None
        self._unscheduled_updates: CALLBACK_TYPE | None = None
        self._retries = 0

    async def async_init(self) -> None:
        """Asynchronous Initialization and registering the update schedule."""
        # config_entry is set in __init__ but mypy seems not to understand...
        if self.config_entry is None:
            raise ValueError("config_entry set in __init__ mysteriously disappeared")

        self._api = await ConexaSMGW.create(
            async_get_clientsession(self.hass),
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_USERNAME],
            self.config_entry.data[CONF_PASSWORD],
        )

        self.gateway_info = self._api.gatewayInfo

        # Check if we got a different URL back -> Something is seriously wrong
        if self._api.m2mUrl != self.config_entry.data["m2mUrl"]:
            raise ConfigEntryError(
                f"SMGW returned {self._api.m2mUrl} but it was originally configured with {self.config_entry.data['m2mUrl']}!"
            )

        # Currently the SMGW provides new data only every 15 minutes at the starting of the hour (in UTC).
        # So we leverage this information to set up a scheduled poll at
        # exactly these times + some seconds to allow for processing.
        self._scheduled_updates = async_track_utc_time_change(
            self.hass,
            self._scheduled_update,
            minute=[0, 15, 30, 45],
            second=40,
        )

    async def _async_update_data(self) -> dict[str, ConexaSMGW.MeterValue]:
        """Fetch data from API endpoint."""
        # If data is None, this is the first refresh cycle
        is_first_update = self.data is None

        _LOGGER.debug("Fetching data from API")
        vals = await self._api.getLatestValues()

        now_utc = dt_util.utcnow()
        _LOGGER.debug("Data fetched at %s: %s", now_utc, vals)
        # On scheduled update the data should be fresh. Do a quick check to confirm.
        # If the smgw was busy and returned old data we try to reschedule in 60 seconds from now 2 times
        # before giving up and accepting the old data, to avoid spamming the smgw with requests.
        if not is_first_update:
            meter_timestamp: str = next(iter(vals.values())).utcTimestamp
            meter_datetime = dt_util.parse_datetime(meter_timestamp)
            if meter_datetime is None:
                _LOGGER.warning("Could not parse meter timestamp: %s", meter_timestamp)
                return vals
            age = (now_utc - meter_datetime).total_seconds()
            _LOGGER.debug("Data age in seconds: %s", age)

            if age <= MAX_MEASUREMENT_AGE:
                self._retries = 0
            elif self._retries < MAX_RETRIES:
                _LOGGER.debug(
                    "Data is quite old (age: %s seconds). Likely because the SMGW was busy, retrying in 60 seconds",
                    age,
                )
                self._unscheduled_updates = async_track_point_in_utc_time(
                    self.hass,
                    self._unscheduled_update,
                    dt_util.utcnow() + timedelta(seconds=60),
                )
                self._retries += 1
            else:
                _LOGGER.debug(
                    "Giving up on retrying, next update will be according to schedule"
                )
                self._retries = 0

        return vals

    async def _scheduled_update(self, now: datetime) -> None:
        """Triggered exactly at the in async_init specified time pattern."""
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

    async def async_shutdown(self) -> None:
        """Cancel any updates before shutting down."""
        if self._scheduled_updates:
            self._scheduled_updates()
            self._scheduled_updates = None

        if self._unscheduled_updates is not None:
            self._unscheduled_updates()
            self._unscheduled_updates = None

        await super().async_shutdown()
