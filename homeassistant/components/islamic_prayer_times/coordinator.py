"""Coordinator for the Islamic prayer times integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from prayer_times_calculator import PrayerTimesCalculator, exceptions
from requests.exceptions import ConnectionError as ConnError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import CONF_CALC_METHOD, DEFAULT_CALC_METHOD, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IslamicPrayerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, datetime]]):
    """Islamic Prayer Client Object."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Islamic Prayer client."""
        self.event_unsub: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )

    @property
    def calc_method(self) -> str:
        """Return the calculation method."""
        return self.config_entry.options.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

    def get_new_prayer_times(self) -> dict[str, str]:
        """Fetch prayer times for today."""
        calc = PrayerTimesCalculator(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            calculation_method=self.calc_method,
            date=str(dt_util.now().date()),
        )
        return calc.fetch_prayer_times()

    @callback
    def async_schedule_future_update(self, midnight_dt: datetime) -> None:
        """Schedule future update for sensors.

        Midnight is a calculated time.  The specifics of the calculation
        depends on the method of the prayer time calculation.  This calculated
        midnight is the time at which the time to pray the Isha prayers have
        expired.

        Calculated Midnight: The Islamic midnight.
        Traditional Midnight: 12:00AM

        Update logic for prayer times:

        If the Calculated Midnight is before the traditional midnight then wait
        until the traditional midnight to run the update.  This way the day
        will have changed over and we don't need to do any fancy calculations.

        If the Calculated Midnight is after the traditional midnight, then wait
        until after the calculated Midnight.  We don't want to update the prayer
        times too early or else the timings might be incorrect.

        Example:
        calculated midnight = 11:23PM (before traditional midnight)
        Update time: 12:00AM

        calculated midnight = 1:35AM (after traditional midnight)
        update time: 1:36AM.

        """
        _LOGGER.debug("Scheduling next update for Islamic prayer times")

        now = dt_util.utcnow()

        if now > midnight_dt:
            next_update_at = midnight_dt + timedelta(days=1, minutes=1)
            _LOGGER.debug(
                "Midnight is after the day changes so schedule update for after Midnight the next day"
            )
        else:
            _LOGGER.debug(
                "Midnight is before the day changes so schedule update for the next start of day"
            )
            next_update_at = dt_util.start_of_local_day(now + timedelta(days=1))

        _LOGGER.debug("Next update scheduled for: %s", next_update_at)

        self.event_unsub = async_track_point_in_time(
            self.hass, self.async_request_update, next_update_at
        )

    async def async_request_update(self, *_) -> None:
        """Request update from coordinator."""
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, datetime]:
        """Update sensors with new prayer times."""
        try:
            prayer_times = await self.hass.async_add_executor_job(
                self.get_new_prayer_times
            )
        except (exceptions.InvalidResponseError, ConnError) as err:
            async_call_later(self.hass, 60, self.async_request_update)
            raise UpdateFailed from err

        prayer_times_info: dict[str, datetime] = {}
        for prayer, time in prayer_times.items():
            if prayer_time := dt_util.parse_datetime(f"{dt_util.now().date()} {time}"):
                prayer_times_info[prayer] = dt_util.as_utc(prayer_time)

        self.async_schedule_future_update(prayer_times_info["Midnight"])
        return prayer_times_info
