"""
Platform to retrieve Islamic prayer times information for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.islamic_prayer_times/
"""
import logging
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_point_in_time

REQUIREMENTS = ['prayer_times_calculator==0.0.3']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'fajr': ['mdi:calendar-clock'],
    'sunrise': ['mdi:calendar-clock'],
    'dhuhr': ['mdi:calendar-clock'],
    'asr': ['mdi:calendar-clock'],
    'maghrib': ['mdi:calendar-clock'],
    'isha': ['mdi:calendar-clock'],
    'midnight': ['mdi:calendar-clock']
}

CONF_CALC_METHOD = 'calculation_method'
CONF_SENSORS = 'sensors'

CALC_METHODS = ['karachi', 'isna', 'mwl', 'makkah']
DEFAULT_CALC_METHOD = 'isna'
DEFAULT_SENSORS = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CALC_METHOD, default=DEFAULT_CALC_METHOD): vol.In(
        CALC_METHODS),
    vol.Optional(CONF_SENSORS, default=DEFAULT_SENSORS):
        vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(
            list(SENSOR_TYPES.keys()))]),
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

    sensor_config = {'lat': latitude, 'long': longitude, 'method': calc_method}

    prayer_times = IslamicPrayerTimesData(sensor_config['lat'],
                                          sensor_config['long'],
                                          sensor_config[
                                              'method']).get_prayer_times()

    sensors = []
    for sensor_type in config[CONF_SENSORS]:
        # Set the initial state of the sensor
        prayer_time = prayer_times[sensor_type.capitalize()]
        sensors.append(IslamicPrayerTimeSensor(sensor_type, prayer_time))

    async_add_entities(sensors, True)

    # schedule the next update for the sensors
    await schedule_future_update(hass, sensors, sensor_config,
                                 prayer_times['Midnight'])


async def schedule_future_update(hass, sensors, sensor_config, midnight_time):
    """Midnight is a calculated time.  The specifics of the calculation
    depends on the method of the prayer time calculation.  This calculated
    midnight is the time at which the time to pray the Isha prayers have
    expired.

    Calculated Midnight: The Islamic midnight.
    Traditional Midnight: 12:00AM

    Update logic for prayer times:

    If the Calculated Midnight is before the traditional midnight then wait
    until the the traditional midnight to run the update.  This way the day
    will have changed over and no fancy calculations.

    If the Calculated Midnight is after the traditional midnight, then wait
    until after the calculated Midnight.  We don't want to update the prayer
    times too early or else the timings will be incorrect."""

    _LOGGER.info("Scheduling next update for Islamic prayer times")

    now = dt_util.as_local(dt_util.now())
    today = now.date()

    midnight_dt_str = '{}::{}'.format(str(today), midnight_time)
    midnight_dt = datetime.strptime(midnight_dt_str, '%Y-%m-%d::%H:%M')

    if now > dt_util.as_local(midnight_dt):
        """Midnight is after day the changes so schedule update for
        after Midnight the next day"""

        _LOGGER.info("Midnight is after day the changes so schedule update "
                     "for after Midnight the next day")

        next_update_at = midnight_dt + timedelta(days=1, minutes=1)
    else:
        """Midnight is before the day changes so schedule update for the
        next start of day"""

        _LOGGER.info(
            "Midnight is before the day changes so schedule update for the "
            "next start of day")

        tomorrow = now + timedelta(days=1, minutes=1)
        next_update_at = dt_util.start_of_local_day(tomorrow)

    # This is only here to test that update is working correctly without
    # having to wait for Midnight
    next_update_at = now + timedelta(seconds=30)

    _LOGGER.info("Next update scheduled for: {}".format(str(next_update_at)))

    async_track_point_in_time(hass,
                              update_sensors(hass, sensors, sensor_config),
                              next_update_at)


async def update_sensors(hass, sensors, sensor_config):
    prayer_times = IslamicPrayerTimesData(sensor_config['lat'],
                                          sensor_config['long'],
                                          sensor_config[
                                              'method']).get_prayer_times()

    for sensor in sensors:
        prayer_time = prayer_times[sensor.sensor_type.capitalize()]
        await sensor.async_update_prayer_time(prayer_time)

    await schedule_future_update(hass, sensors,
                                 sensor_config,
                                 prayer_times['Midnight'])


class IslamicPrayerTimesData:
    def __init__(self, latitude, longitude, calc_method):
        self.latitude = latitude
        self.longitude = longitude
        self.calc_method = calc_method

    def get_prayer_times(self):
        from prayer_times_calculator import PrayerTimesCalculator

        now = dt_util.as_local(dt_util.now())
        today = now.date()

        calc = PrayerTimesCalculator(latitude=self.latitude,
                                     longitude=self.longitude,
                                     calculation_method=self.calc_method,
                                     date=str(today))
        return calc.fetch_prayer_times()


class IslamicPrayerTimeSensor(Entity):
    """Representation of an Islamic prayer time sensor."""

    ENTITY_ID_FORMAT = 'sensor.islamic_prayer_time_{}'

    def __init__(self, sensor_type, prayer_time):
        """Initialize the Islamic prayer time sensor."""
        self.sensor_type = sensor_type
        self.entity_id = self.ENTITY_ID_FORMAT.format(self.sensor_type)
        self._state = prayer_time
        self._date_time_format = '%Y-%m-%d::%H:%M'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.sensor_type.capitalize()

    @property
    def icon(self):
        """Icon to display in the front end."""
        return SENSOR_TYPES[self.sensor_type][0]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_fire_prayer_event(self, prayer: str):
        _LOGGER.debug("Firing Event for: {}".format(prayer))
        self.hass.bus.async_fire('islamic_prayer_time', {'prayer': prayer})

    async def async_set_event_trigger(self, prayer_time, prayer_name):
        now = dt_util.as_local(dt_util.now())
        today = now.date()

        date_time_str = '{}::{}'.format(str(today), prayer_time)
        trigger_time = datetime.strptime(date_time_str,
                                         self._date_time_format)

        if dt_util.as_utc(now) < dt_util.as_utc(trigger_time):
            """Only create an event for prayers times in the future"""

            _LOGGER.debug("Creating event trigger for: {}".format(
                prayer_name))
            async_track_point_in_time(self.hass,
                                      self.async_fire_prayer_event(
                                          prayer_name),
                                      trigger_time)
        else:
            _LOGGER.debug("{} is in the past so we won't create an "
                          "event".format(prayer_name))

    async def async_update_prayer_time(self, prayer_time):
        _LOGGER.debug("Inside async_update_prayer_time")
        _LOGGER.debug("Updating {}'s prayer time to: {}".format(
            self.sensor_type, prayer_time))
        self._state = prayer_time
        await self.async_set_event_trigger(self._state, self.sensor_type)
