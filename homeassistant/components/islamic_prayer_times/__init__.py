"""The islamic_prayer_times component."""
from datetime import datetime, timedelta
import logging

from prayer_times_calculator import PrayerTimesCalculator, exceptions


import voluptuous as vol
import homeassistant.util.dt as dt_util

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_time

from .const import (
    DOMAIN,
    CONF_CALC_METHOD,
    DEFAULT_CALC_METHOD,
    CALC_METHODS,
    DATA_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_CALC_METHOD, default=DEFAULT_CALC_METHOD): vol.In(
                CALC_METHODS
            ),
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Import the Islamic Prayer component from config."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Islamic Prayer Component."""
    client = IslamicPrayerClient(hass, config_entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = client

    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Transmission Entry from config_entry."""

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    hass.data.pop(DOMAIN)

    return True


class IslamicPrayerClient:
    """Islamic Prayer Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Islamic Prayer client."""
        self.hass = hass
        self.config_entry = config_entry
        self.prayer_times_info = None
        self.available = None

    async def get_new_prayer_times(self):
        """Fetch prayer times for today."""

        calc = PrayerTimesCalculator(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            calculation_method=self.config_entry.options[CONF_CALC_METHOD],
            date=str(dt_util.now().date()),
        )
        self.prayer_times_info = calc.fetch_prayer_times()

    async def schedule_future_update(self):
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

        midnight_time = self.prayer_times_info["Midnight"]
        now = dt_util.as_local(dt_util.now())
        today = now.date()

        midnight_dt_str = "{}::{}".format(str(today), midnight_time)
        midnight_dt = datetime.strptime(midnight_dt_str, "%Y-%m-%d::%H:%M")

        if now > dt_util.as_local(midnight_dt):
            _LOGGER.debug(
                "Midnight is after day the changes so schedule update "
                "for after Midnight the next day"
            )

            next_update_at = midnight_dt + timedelta(days=1, minutes=1)
        else:
            _LOGGER.debug(
                "Midnight is before the day changes so schedule update for the "
                "next start of day"
            )

            tomorrow = now + timedelta(days=1)
            next_update_at = dt_util.start_of_local_day(tomorrow)

        _LOGGER.debug("Next update scheduled for: %s", str(next_update_at))

        async_track_point_in_time(self.hass, self.async_update, next_update_at)

    async def async_update(self):
        """Update sensors with new prayer times."""
        try:
            await self.get_new_prayer_times()
            await self.schedule_future_update()
            self.available = True
            _LOGGER.debug("New prayer times retrieved.  Updating sensors.")

        except exceptions.InvalidResponseError:
            self.available = False

        async_dispatcher_send(self.hass, DATA_UPDATED)

    async def async_setup(self):
        """Set up the Islamic prayer client."""

        self.add_options()

        try:
            await self.get_new_prayer_times()
        except exceptions.InvalidResponseError:
            raise ConfigEntryNotReady

        await self.async_update()

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "sensor"
            )
        )

        return True

    def add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            calc_method = self.config_entry.data.get(
                CONF_CALC_METHOD, DEFAULT_CALC_METHOD
            )

            self.hass.config_entries.async_update_entry(
                self.config_entry, options={CONF_CALC_METHOD: calc_method}
            )

    @staticmethod
    def get_prayer_time_as_dt(prayer_time):
        """Create a datetime object for the respective prayer time."""
        today = dt_util.now().date()
        date_time_str = "{} {}".format(str(today), prayer_time)
        pt_dt = dt_util.parse_datetime(date_time_str)
        return pt_dt
