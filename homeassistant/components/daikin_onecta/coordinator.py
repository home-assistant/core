"""Coordinator for Daikin Onecta integration."""

from datetime import datetime, time, timedelta, tzinfo
import logging
from math import ceil
import random
from typing import override

from daikin_onecta.exceptions import OnectaConnectionError, OnectaRateLimitError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .daikin_api import DaikinApi
from .device import DaikinOnectaDevice

_LOGGER = logging.getLogger(__name__)

_HIGH_SCAN_INTERVAL = timedelta(minutes=10)
_LOW_SCAN_INTERVAL = timedelta(minutes=30)
_HIGH_SCAN_START = time(7)
_LOW_SCAN_START = time(22)
_POST_WRITE_COOLDOWN = timedelta(seconds=30)
_DEFAULT_DAILY_CALL_LIMIT = 200
_POLLING_BUDGET_FRACTION = 0.55
_MINIMUM_POLL_INTERVAL = timedelta(minutes=3)

type DaikinOnectaConfigEntry = ConfigEntry[OnectaDataUpdateCoordinator]


class OnectaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DaikinOnectaDevice]]):
    """Class to manage fetching data from the API."""

    config_entry: DaikinOnectaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DaikinOnectaConfigEntry,
        daikin_api: DaikinApi,
    ) -> None:
        """Initialize."""
        self.options = config_entry.options
        self._daikin_api = daikin_api

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._determine_update_interval(),
        )

        _LOGGER.info(
            "Daikin coordinator initialized with %s interval",
            self.update_interval,
        )

    @property
    def api(self) -> DaikinApi:
        """Return the Daikin API client."""
        return self._daikin_api

    async def _async_update_data_from_cloud(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch the latest device state from Daikin."""
        _LOGGER.debug("Daikin coordinator start _async_update_data")

        devices = self.data or {}
        if (
            self.api.last_patch_call is not None
            and (dt_util.utcnow() - self.api.last_patch_call).total_seconds()
            < _POST_WRITE_COOLDOWN.total_seconds()
        ):
            self.update_interval = _POST_WRITE_COOLDOWN
            _LOGGER.debug(
                "API UPDATE skipped (just updated from UI)",
            )
        else:
            try:
                cloud_devices = await self.api.get_cloud_device_details(
                    cooldown=_POST_WRITE_COOLDOWN
                )
            except OnectaRateLimitError as err:
                _LOGGER.warning(
                    "Daikin API rate limit reached; retrying after %s seconds",
                    err.retry_after,
                )
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="rate_limit_exceeded",
                    retry_after=err.retry_after,
                ) from err
            except OnectaConnectionError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_failed",
                ) from err

            if cloud_devices is None:
                self.update_interval = _POST_WRITE_COOLDOWN
                _LOGGER.debug("API UPDATE skipped (just updated from UI)")
            else:
                cloud_device_ids = {device.id for device in cloud_devices}
                for device_id, device in devices.items():
                    if device_id not in cloud_device_ids:
                        device.mark_unavailable()

                for dev_data in cloud_devices:
                    if dev_data.id in devices:
                        device = devices[dev_data.id]
                        device.set_device_data(dev_data)
                        device.async_register_ha_device(self.hass, self.config_entry)
                    else:
                        device = DaikinOnectaDevice(dev_data)
                        # Register the gateway device before entity platforms are set
                        # up so they can link back to this gateway device.
                        device.async_register_ha_device(self.hass, self.config_entry)
                        devices[dev_data.id] = device

                self.update_interval = self._determine_update_interval()

        _LOGGER.debug(
            "Daikin coordinator finished _async_update_data, next interval %s",
            self.update_interval,
        )
        return devices

    @override
    async def _async_update_data(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch data for the Home Assistant coordinator interface."""
        return await self._async_update_data_from_cloud()

    def update_settings(self, config_entry: ConfigEntry) -> bool:
        """Apply updated config entry options and report whether they changed."""
        if self.options == config_entry.options:
            return False

        _LOGGER.debug("Daikin coordinator updating settings")
        self.options = config_entry.options
        return True

    def _determine_update_interval(self) -> timedelta:
        """Determine the next polling interval."""
        now = dt_util.now()
        high_interval, low_interval = self._polling_intervals()
        scan_interval = int(low_interval.total_seconds())
        high_scan_interval = int(high_interval.total_seconds())
        hs = _HIGH_SCAN_START
        ls = _LOW_SCAN_START
        in_high_frequency_window = self._in_between(now.time(), hs, ls)
        if in_high_frequency_window:
            scan_interval = high_scan_interval
        else:
            # When switching from high to low frequency polling we need to randomize the first
            # poll so that we spread the load to daikin, so for example when we have a low start at
            # 22:00 and a high scan interval of 9 minutes we randomize the next poll when it is
            # between 22:00 and 22:09
            end_time = (
                dt_util.start_of_local_day()
                + timedelta(
                    hours=ls.hour,
                    minutes=ls.minute,
                    seconds=ls.second + high_scan_interval,
                )
            ).time()
            if self._in_between(now.time(), ls, end_time):
                scan_interval = random.randint(high_scan_interval, scan_interval)

        if hs != ls:
            boundary = ls if in_high_frequency_window else hs
            now_utc = dt_util.as_utc(now)
            next_boundary = datetime.combine(
                now.date(), boundary, dt_util.DEFAULT_TIME_ZONE
            ).replace(fold=now.fold)
            if dt_util.as_utc(next_boundary) <= now_utc:
                # During the first occurrence of the daylight-saving rollback
                # hour, the same local boundary can occur once more today.
                repeated_boundary = next_boundary.replace(fold=1)
                if dt_util.as_utc(repeated_boundary) > now_utc:
                    next_boundary = repeated_boundary
                else:
                    next_boundary = datetime.combine(
                        now.date() + timedelta(days=1),
                        boundary,
                        dt_util.DEFAULT_TIME_ZONE,
                    )
            next_boundary_utc = dt_util.as_utc(next_boundary)
            boundary_delay = int((next_boundary_utc - now_utc).total_seconds())
            if self._is_nonexistent_local_time(next_boundary):
                # A local boundary in the spring-forward gap resolves later
                # than the clock transition. Poll at the transition so the
                # next calculation can apply the active window's interval.
                boundary_delay = int(
                    (
                        self._next_clock_transition(
                            now_utc, next_boundary_utc, next_boundary.tzinfo
                        )
                        - now_utc
                    ).total_seconds()
                )
                scan_interval = min(
                    scan_interval, max(high_scan_interval, boundary_delay)
                )
            else:
                # Keep a valid polling interval when the next boundary is less
                # than one high-frequency interval away. In particular, converting
                # a fractional-second delay to an integer must not result in zero.
                scan_interval = max(
                    high_scan_interval, min(scan_interval, boundary_delay)
                )

        return timedelta(seconds=scan_interval)

    def _polling_intervals(self) -> tuple[timedelta, timedelta]:
        """Return polling intervals within the available daily API-call budget."""
        rate_limit = self.api.rate_limits.get("day")
        daily_limit = (
            rate_limit
            if isinstance(rate_limit, int) and rate_limit > 0
            else _DEFAULT_DAILY_CALL_LIMIT
        )
        daily_budget = max(2, int(daily_limit * _POLLING_BUDGET_FRACTION))

        high_window_seconds = (
            datetime.combine(datetime.min, _LOW_SCAN_START)
            - datetime.combine(datetime.min, _HIGH_SCAN_START)
        ).total_seconds() % timedelta(days=1).total_seconds()
        low_window_seconds = timedelta(days=1).total_seconds() - high_window_seconds
        interval_ratio = _LOW_SCAN_INTERVAL / _HIGH_SCAN_INTERVAL
        minimum_interval = int(_MINIMUM_POLL_INTERVAL.total_seconds())
        high_interval = max(
            minimum_interval,
            ceil(
                (high_window_seconds + low_window_seconds / interval_ratio)
                / daily_budget
            ),
        )
        low_interval = max(minimum_interval, ceil(high_interval * interval_ratio))

        while (
            ceil(high_window_seconds / high_interval)
            + ceil(low_window_seconds / low_interval)
            > daily_budget
        ):
            high_interval += 1
            low_interval = max(minimum_interval, ceil(high_interval * interval_ratio))

        _LOGGER.debug(
            "Daikin polling uses %s of %s daily calls: %s daytime, %s overnight",
            daily_budget,
            daily_limit,
            timedelta(seconds=high_interval),
            timedelta(seconds=low_interval),
        )
        return timedelta(seconds=high_interval), timedelta(seconds=low_interval)

    @staticmethod
    def _in_between(now: time, start: time, end: time) -> bool:
        """Return whether now is between start and end, including overnight ranges."""
        if start <= end:
            return start <= now < end
        return start <= now or now < end

    @staticmethod
    def _is_nonexistent_local_time(value: datetime) -> bool:
        """Return whether an aware datetime falls within a clock-forward gap."""
        assert value.tzinfo is not None
        return dt_util.as_utc(value).astimezone(value.tzinfo).replace(
            tzinfo=None
        ) != value.replace(tzinfo=None)

    @staticmethod
    def _next_clock_transition(
        start: datetime, end: datetime, timezone: tzinfo | None
    ) -> datetime:
        """Return the first UTC offset transition between two UTC datetimes."""
        assert timezone is not None
        offset = start.astimezone(timezone).utcoffset()
        assert end.astimezone(timezone).utcoffset() != offset

        while end - start > timedelta(seconds=1):
            midpoint = start + (end - start) / 2
            if midpoint.astimezone(timezone).utcoffset() == offset:
                start = midpoint
            else:
                end = midpoint
        return end
