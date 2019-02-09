"""
Platform to retrieve Islamic prayer times information for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.islamic_prayer_times/
"""
import logging
from datetime import datetime, timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_time

REQUIREMENTS = ['prayer_times_calculator==0.0.3']

_LOGGER = logging.getLogger(__name__)

PRAYER_TIMES_ICON = 'mdi:calendar-clock'

SENSOR_TYPES = ['fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha',
                'midnight']

CONF_CALC_METHOD = 'calculation_method'
CONF_SENSORS = 'sensors'

CALC_METHODS = ['karachi', 'isna', 'mwl', 'makkah']
DEFAULT_CALC_METHOD = 'isna'
DEFAULT_SENSORS = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CALC_METHOD, default=DEFAULT_CALC_METHOD): vol.In(
        CALC_METHODS),
    vol.Optional(CONF_SENSORS, default=DEFAULT_SENSORS):
        vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)]),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Islamic prayer times sensor platform."""
    latitude = hass.config.latitude
    longitude = hass.config.longitude
    calc_method = config.get(CONF_CALC_METHOD)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    prayer_times_data = IslamicPrayerTimesData(latitude,
                                               longitude,
                                               calc_method)

    prayer_times = prayer_times_data.get_new_prayer_times()

    sensors = []
    for sensor_type in config[CONF_SENSORS]:
        sensors.append(IslamicPrayerTimeSensor(sensor_type, prayer_times_data))

    async_add_entities(sensors, True)

    # schedule the next update for the sensors
    await schedule_future_update(hass, sensors, prayer_times['Midnight'],
                                 prayer_times_data)


async def schedule_future_update(hass, sensors, midnight_time,
                                 prayer_times_data):
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

    now = dt_util.as_local(dt_util.now())
    today = now.date()

    midnight_dt_str = '{}::{}'.format(str(today), midnight_time)
    midnight_dt = datetime.strptime(midnight_dt_str, '%Y-%m-%d::%H:%M')

    if now > dt_util.as_local(midnight_dt):
        _LOGGER.debug("Midnight is after day the changes so schedule update "
                      "for after Midnight the next day")

        next_update_at = midnight_dt + timedelta(days=1, minutes=1)
    else:
        _LOGGER.debug(
            "Midnight is before the day changes so schedule update for the "
            "next start of day")

        tomorrow = now + timedelta(days=1)
        next_update_at = dt_util.start_of_local_day(tomorrow)

    _LOGGER.debug("Next update scheduled for: %s", str(next_update_at))

    async def update_sensors(_):
        """Update sensors with new prayer times."""
        # Update prayer times
        prayer_times = prayer_times_data.get_new_prayer_times()

        _LOGGER.debug("New prayer times retrieved.  Updating sensors.")

        # Update all prayer times sensors
        for sensor in sensors:
            sensor.async_schedule_update_ha_state(True)

        # Schedule next update
        await schedule_future_update(hass, sensors, prayer_times['Midnight'],
                                     prayer_times_data)

    async_track_point_in_time(hass,
                              update_sensors,
                              next_update_at)


class IslamicPrayerTimesData:
    """Data object for Islamic prayer times."""

    def __init__(self, latitude, longitude, calc_method):
        """Create object to hold data."""
        self.latitude = latitude
        self.longitude = longitude
        self.calc_method = calc_method
        self.prayer_times_info = None

    def get_new_prayer_times(self):
        """Fetch prayer times for today."""
        from prayer_times_calculator import PrayerTimesCalculator

        today = datetime.today().strftime('%Y-%m-%d')

        calc = PrayerTimesCalculator(latitude=self.latitude,
                                     longitude=self.longitude,
                                     calculation_method=self.calc_method,
                                     date=str(today))

        self.prayer_times_info = calc.fetch_prayer_times()
        return self.prayer_times_info


class IslamicPrayerTimeSensor(Entity):
    """Representation of an Islamic prayer time sensor."""

    ENTITY_ID_FORMAT = 'sensor.islamic_prayer_time_{}'

    def __init__(self, sensor_type, prayer_times_data):
        """Initialize the Islamic prayer time sensor."""
        self.sensor_type = sensor_type
        self.entity_id = self.ENTITY_ID_FORMAT.format(self.sensor_type)
        self.prayer_times_data = prayer_times_data
        self._name = self.sensor_type.capitalize()
        self._device_class = DEVICE_CLASS_TIMESTAMP
        prayer_time = self.prayer_times_data.prayer_times_info[
            self._name]
        pt_dt = self.get_prayer_time_as_dt(prayer_time)
        self._state = pt_dt.isoformat()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to display in the front end."""
        return PRAYER_TIMES_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @staticmethod
    def get_prayer_time_as_dt(prayer_time):
        """Create a datetime object for the respective prayer time."""
        today = datetime.today().strftime('%Y-%m-%d')
        date_time_str = '{} {}'.format(str(today), prayer_time)
        pt_dt = dt_util.parse_datetime(date_time_str)
        return pt_dt

    async def async_update(self):
        """Update the sensor."""
        prayer_time = self.prayer_times_data.prayer_times_info[self.name]
        pt_dt = self.get_prayer_time_as_dt(prayer_time)
        self._state = pt_dt.isoformat()
