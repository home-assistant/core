"""Coordinator for the Islamic prayer times integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any, cast

from prayer_times_calculator_offline import PrayerTimesCalculator

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CALC_METHOD,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    DEFAULT_CALC_METHOD,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class IslamicPrayerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, datetime]]):
    """Islamic Prayer Client Object."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Islamic Prayer client."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.latitude = self.config_entry.data[CONF_LATITUDE]
        self.longitude = self.config_entry.data[CONF_LONGITUDE]
        self.event_unsub: CALLBACK_TYPE | None = None

    @property
    def calc_method(self) -> str:
        """Return the calculation method."""
        return self.config_entry.options.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

    @property
    def lat_adj_method(self) -> str:
        """Return the latitude adjustment method."""
        return str(
            self.config_entry.options.get(
                CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD
            ).replace("_", " ")
        )

    @property
    def midnight_mode(self) -> str:
        """Return the midnight mode."""
        return self.config_entry.options.get(CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE)

    @property
    def school(self) -> str:
        """Return the school."""
        return self.config_entry.options.get(CONF_SCHOOL, DEFAULT_SCHOOL)

    def get_new_prayer_times(self, for_date: date) -> dict[str, Any]:
        """Fetch prayer times for the specified date."""
        calc = PrayerTimesCalculator(
            latitude=self.latitude,
            longitude=self.longitude,
            calculation_method=self.calc_method,
            latitudeAdjustmentMethod=self.lat_adj_method,
            midnightMode=self.midnight_mode,
            school=self.school,
            date=str(for_date),
            iso8601=True,
        )
        return cast(dict[str, Any], calc.fetch_prayer_times())

    @callback
    def async_schedule_future_update(self, midnight_dt: datetime) -> None:
        """Schedule future update for sensors.

        The least surprising behaviour is to load the next day's prayer times only
        after the current day's prayers are complete. We will take the fiqhi opinion
        that Isha should be prayed before Islamic midnight (which may be before or after 12:00 midnight),
        and thus we will switch to the next day's timings at Islamic midnight.

        The +1s is to ensure that any automations predicated on the arrival of Islamic midnight will run.

        """
        _LOGGER.debug("Scheduling next update for Islamic prayer times")

        self.event_unsub = async_track_point_in_time(
            self.hass, self.async_request_update, midnight_dt + timedelta(seconds=1)
        )

    async def async_request_update(self, _: datetime) -> None:
        """Request update from coordinator."""
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, datetime]:
        """Update sensors with new prayer times.

        Prayer time calculations "roll over" at 12:00 midnight - but this does not mean that all prayers
        occur within that Gregorian calendar day. For instance Jasper, Alta. sees Isha occur after 00:00 in the summer.
        It is similarly possible (albeit less likely) that Fajr occurs before 00:00.

        As such, to ensure that no prayer times are "unreachable" (e.g. we always see the Isha timestamp pass before loading the next day's times),
        we calculate 3 days' worth of times (-1, 0, +1 days) and select the appropriate set based on Islamic midnight.

        The calculation is inexpensive, so there is no need to cache it.
        """

        # Zero out the us component to maintain consistent rollover at T+1s
        now = dt_util.now().replace(microsecond=0)
        yesterday_times = self.get_new_prayer_times((now - timedelta(days=1)).date())
        today_times = self.get_new_prayer_times(now.date())
        tomorrow_times = self.get_new_prayer_times((now + timedelta(days=1)).date())

        if (
            yesterday_midnight := dt_util.parse_datetime(yesterday_times["Midnight"])
        ) and now <= yesterday_midnight:
            prayer_times = yesterday_times
        elif (
            tomorrow_midnight := dt_util.parse_datetime(today_times["Midnight"])
        ) and now > tomorrow_midnight:
            prayer_times = tomorrow_times
        else:
            prayer_times = today_times

        # introduced in prayer-times-calculator 0.0.8
        prayer_times.pop("date", None)

        prayer_times_info: dict[str, datetime] = {}
        for prayer, time in prayer_times.items():
            if prayer_time := dt_util.parse_datetime(time):
                prayer_times_info[prayer] = dt_util.as_utc(prayer_time)

        self.async_schedule_future_update(prayer_times_info["Midnight"])
        return prayer_times_info
