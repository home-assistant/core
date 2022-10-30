"""The islamic_prayer_times component."""
from datetime import timedelta
import logging

from prayer_times_calculator import PrayerTimesCalculator, exceptions
from requests.exceptions import ConnectionError as ConnError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
import homeassistant.util.dt as dt_util

from .const import CONF_CALC_METHOD, DATA_UPDATED, DEFAULT_CALC_METHOD, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Islamic Prayer Component."""
    client = IslamicPrayerClient(hass, config_entry)

    await client.async_setup()

    hass.data.setdefault(DOMAIN, client)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Islamic Prayer entry from config_entry."""
    if hass.data[DOMAIN].event_unsub:
        hass.data[DOMAIN].event_unsub()
    hass.data.pop(DOMAIN)
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


class IslamicPrayerClient:
    """Islamic Prayer Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Islamic Prayer client."""
        self.hass = hass
        self.config_entry = config_entry
        self.prayer_times_info = {}
        self.available = True
        self.event_unsub = None

    @property
    def calc_method(self):
        """Return the calculation method."""
        return self.config_entry.options[CONF_CALC_METHOD]

    def get_new_prayer_times(self):
        """Fetch prayer times for today."""
        calc = PrayerTimesCalculator(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            calculation_method=self.calc_method,
            date=str(dt_util.now().date()),
        )
        return calc.fetch_prayer_times()

    async def async_schedule_future_update(self):
        """Schedule future update for sensors.

        Always schedule update on 02:01 AM local time to anticipate daylight saving time changes.

        Islamic calculated midnight would be almost always before 02:00 AM, so it should not need
        special handling.
        The caveat is that the sensor would be inaccurate between 00:00-02:00AM each day.

        """
        _LOGGER.debug("Scheduling next update for Islamic prayer times")

        now = dt_util.utcnow()

        dst_change = dt_util.start_of_local_day(now) + timedelta(hours=2, minutes=1)

        if now < dst_change:
            next_update_at = dst_change
            _LOGGER.debug(
                "Current time is before 02:01 AM so update is scheduled on 2:01 AM today to anticipate DST change"
            )
        else:
            next_update_at = dst_change + timedelta(days=1)
            _LOGGER.debug("Schedule update for 02:01 AM the next day")

        _LOGGER.info("Next update scheduled for: %s", next_update_at)

        self.event_unsub = async_track_point_in_time(
            self.hass, self.async_update, next_update_at
        )

    async def async_update(self, *_):
        """Update sensors with new prayer times."""
        try:
            prayer_times = await self.hass.async_add_executor_job(
                self.get_new_prayer_times
            )
            self.available = True
        except (exceptions.InvalidResponseError, ConnError):
            self.available = False
            _LOGGER.debug("Error retrieving prayer times")
            async_call_later(self.hass, 60, self.async_update)
            return

        for prayer, time in prayer_times.items():
            self.prayer_times_info[prayer] = dt_util.parse_datetime(
                f"{dt_util.now().date()} {time}"
            )
        await self.async_schedule_future_update()

        _LOGGER.debug("New prayer times retrieved. Updating sensors")
        async_dispatcher_send(self.hass, DATA_UPDATED)

    async def async_setup(self):
        """Set up the Islamic prayer client."""
        await self.async_add_options()

        try:
            await self.hass.async_add_executor_job(self.get_new_prayer_times)
        except (exceptions.InvalidResponseError, ConnError) as err:
            raise ConfigEntryNotReady from err

        await self.async_update()
        self.config_entry.add_update_listener(self.async_options_updated)

        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

        return True

    async def async_add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            data = dict(self.config_entry.data)
            calc_method = data.pop(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, options={CONF_CALC_METHOD: calc_method}
            )

    @staticmethod
    async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Triggered by config entry options updates."""
        if hass.data[DOMAIN].event_unsub:
            hass.data[DOMAIN].event_unsub()
        await hass.data[DOMAIN].async_update()
