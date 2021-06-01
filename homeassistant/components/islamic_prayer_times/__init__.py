"""The islamic_prayer_times component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Callable

from prayer_times_calculator import PrayerTimesCalculator, exceptions
from requests.exceptions import ConnectionError as ConnError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CALC_METHODS,
    CONF_CALC_METHOD,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    CONF_TUNE,
    DEFAULT_CALC_METHOD,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Islamic Prayer Component."""
    coordinator = IslamicPrayerDataCoordinator(hass, config_entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, coordinator)
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:

        new_options = {**config_entry.options}
        calc_method = new_options.get(CONF_CALC_METHOD)
        if calc_method:
            for method in CALC_METHODS:
                if calc_method == method.lower():
                    new_options[CONF_CALC_METHOD] = method
                    break

        config_entry.version = 2
        hass.config_entries.async_update_entry(
            config_entry,
            options={**config_entry.options, **new_options},
        )
    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Islamic Prayer entry from config_entry."""
    if hass.data[DOMAIN].event_unsub:
        hass.data[DOMAIN].event_unsub()
    if hass.data[DOMAIN].unsub_listener:
        hass.data[DOMAIN].unsub_listener()

    hass.data.pop(DOMAIN)
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


class IslamicPrayerDataCoordinator(DataUpdateCoordinator):
    """Islamic Prayer Client Object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Islamic Prayer client."""
        self.hass = hass
        self.config_entry = config_entry
        self.event_unsub = None
        self.unsub_listener: Callable | None = None
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
        )

    @property
    def calc_method(self):
        """Return the calculation method."""
        return self.config_entry.options.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

    @property
    def extra_params(self) -> dict:
        """Return the calculation params."""
        _params = {}
        _params[CONF_SCHOOL] = self.config_entry.options.get(
            CONF_SCHOOL, DEFAULT_SCHOOL
        )
        _params[CONF_MIDNIGHT_MODE] = self.config_entry.options.get(
            CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE
        )
        _params[CONF_LAT_ADJ_METHOD] = self.config_entry.options.get(
            CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD
        )
        if self.config_entry.options.get(CONF_TUNE):
            _params[CONF_TUNE] = True
            for sensor_tune, offset in self.config_entry.options[CONF_TUNE].items():
                _params[sensor_tune] = offset
        return _params

    def get_new_prayer_times(self) -> dict:
        """Fetch prayer times for today."""
        calc = PrayerTimesCalculator(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            calculation_method=self.calc_method,
            date=str(dt_util.now().date()),
            **self.extra_params,
        )
        return calc.fetch_prayer_times()

    async def async_schedule_future_update(self, midnight_dt) -> None:
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

        if now > dt_util.as_utc(midnight_dt):
            next_update_at = midnight_dt + timedelta(days=1, minutes=1)
            _LOGGER.debug(
                "Midnight is after day the changes so schedule update for after Midnight the next day"
            )
        else:
            _LOGGER.debug(
                "Midnight is before the day changes so schedule update for the next start of day"
            )
            next_update_at = dt_util.start_of_local_day(now + timedelta(days=1))

        _LOGGER.info("Next update scheduled for: %s", next_update_at)

        self.event_unsub = self.hass.helpers.event.async_track_point_in_time(
            self.async_request_update, next_update_at
        )

    async def async_request_update(self, *_) -> None:
        """Request update from coordinator."""
        await self.async_request_refresh()

    async def async_update(self) -> dict:
        """Update sensors with new prayer times."""
        try:
            prayer_times = await self.hass.async_add_executor_job(
                self.get_new_prayer_times
            )
        except (exceptions.InvalidResponseError, ConnError) as err:
            self.hass.helpers.event.async_call_later(60, self.async_request_update)
            raise UpdateFailed from err

        prayer_times_info = {}
        for prayer, time in prayer_times.items():
            prayer_times_info[prayer] = dt_util.parse_datetime(
                f"{dt_util.now().date()} {time}"
            )
        await self.async_schedule_future_update(prayer_times_info["Midnight"])
        return prayer_times_info

    async def async_setup(self) -> None:
        """Set up the Islamic prayer client."""
        try:
            await self.hass.async_add_executor_job(self.get_new_prayer_times)
        except (exceptions.InvalidResponseError, ConnError) as err:
            raise ConfigEntryNotReady from err

        self.unsub_listener = self.config_entry.add_update_listener(
            async_options_updated
        )


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    if hass.data[DOMAIN].event_unsub:
        hass.data[DOMAIN].event_unsub()
    await hass.data[DOMAIN].async_request_refresh()
