"""
Platform to retrieve Jewish calendar information for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.jewish_calendar/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, SUN_EVENT_SUNSET)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import get_astral_event_date
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['hdate==0.8.7']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'date': ['Date', 'mdi:judaism'],
    'weekly_portion': ['Parshat Hashavua', 'mdi:book-open-variant'],
    'holiday_name': ['Holiday', 'mdi:calendar-star'],
    'holyness': ['Holyness', 'mdi:counter'],
    'first_light': ['Alot Hashachar', 'mdi:weather-sunset-up'],
    'gra_end_shma': ['Latest time for Shm"a GR"A', 'mdi:calendar-clock'],
    'mga_end_shma': ['Latest time for Shm"a MG"A', 'mdi:calendar-clock'],
    'plag_mincha': ['Plag Hamincha', 'mdi:weather-sunset-down'],
    'first_stars': ['T\'set Hakochavim', 'mdi:weather-night'],
    'upcoming_shabbat_candle_lighting': ['Upcoming Shabbat Candle Lighting',
                                         'mdi:candle'],
    'upcoming_shabbat_havdalah': ['Upcoming Shabbat Havdalah',
                                  'mdi:weather-night'],
    'upcoming_candle_lighting': ['Upcoming Candle Lighting', 'mdi:candle'],
    'upcoming_havdalah': ['Upcoming Havdalah', 'mdi:weather-night'],
    'issur_melacha_in_effect': ['Issur Melacha in Effect',
                                'mdi:power-plug-off'],
    'omer_count': ['Day of the Omer', 'mdi:counter'],
}

CONF_DIASPORA = 'diaspora'
CONF_LANGUAGE = 'language'
CONF_SENSORS = 'sensors'
CONF_CANDLE_LIGHT_MINUTES = 'candle_lighting_minutes_before_sunset'
CONF_HAVDALAH_OFFSET_MINUTES = 'havdalah_minutes_after_sunset'

CANDLE_LIGHT_DEFAULT = 18

DEFAULT_NAME = 'Jewish Calendar'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DIASPORA, default=False): cv.boolean,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_LANGUAGE, default='english'):
        vol.In(['hebrew', 'english']),
    vol.Optional(CONF_CANDLE_LIGHT_MINUTES, default=CANDLE_LIGHT_DEFAULT): int,
    # Default of 0 means use 8.5 degrees / 'three_stars' time.
    vol.Optional(CONF_HAVDALAH_OFFSET_MINUTES, default=0): int,
    vol.Optional(CONF_SENSORS, default=['date']):
        vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)]),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Jewish calendar sensor platform."""
    language = config.get(CONF_LANGUAGE)
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    diaspora = config.get(CONF_DIASPORA)
    candle_lighting_offset = config.get(CONF_CANDLE_LIGHT_MINUTES)
    havdalah_offset = config.get(CONF_HAVDALAH_OFFSET_MINUTES)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    dev = []
    for sensor_type in config[CONF_SENSORS]:
        dev.append(JewishCalSensor(
            name, language, sensor_type, latitude, longitude,
            hass.config.time_zone, diaspora, candle_lighting_offset,
            havdalah_offset))
    async_add_entities(dev, True)


class JewishCalSensor(Entity):
    """Representation of an Jewish calendar sensor."""

    def __init__(
            self, name, language, sensor_type, latitude, longitude, timezone,
            diaspora, candle_lighting_offset=CANDLE_LIGHT_DEFAULT,
            havdalah_offset=0):
        """Initialize the Jewish calendar sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._hebrew = (language == 'hebrew')
        self._state = None
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.diaspora = diaspora
        self.candle_lighting_offset = candle_lighting_offset
        self.havdalah_offset = havdalah_offset
        _LOGGER.debug("Sensor %s initialized", self.type)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def icon(self):
        """Icon to display in the front end."""
        return SENSOR_TYPES[self.type][1]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update the state of the sensor."""
        import hdate

        now = dt_util.as_local(dt_util.now())
        _LOGGER.debug("Now: %s Timezone = %s", now, now.tzinfo)

        today = now.date()
        sunset = dt_util.as_local(get_astral_event_date(
            self.hass, SUN_EVENT_SUNSET, today))

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        location = hdate.Location(latitude=self.latitude,
                                  longitude=self.longitude,
                                  timezone=self.timezone,
                                  diaspora=self.diaspora)

        def make_zmanim(date):
            """Create a Zmanim object."""
            return hdate.Zmanim(
                date=date, location=location,
                candle_lighting_offset=self.candle_lighting_offset,
                havdalah_offset=self.havdalah_offset, hebrew=self._hebrew)

        date = hdate.HDate(
            today, diaspora=self.diaspora, hebrew=self._hebrew)
        lagging_date = date

        # Advance Hebrew date if sunset has passed.
        # Not all sensors should advance immediately when the Hebrew date
        # officially changes (i.e. after sunset), hence lagging_date.
        if now > sunset:
            date = date.next_day
        today_times = make_zmanim(today)
        if today_times.havdalah and now > today_times.havdalah:
            lagging_date = lagging_date.next_day

        # Terminology note: by convention in py-libhdate library, "upcoming"
        # refers to "current" or "upcoming" dates.
        if self.type == 'date':
            self._state = date.hebrew_date
        elif self.type == 'weekly_portion':
            # Compute the weekly portion based on the upcoming shabbat.
            self._state = lagging_date.upcoming_shabbat.parasha
        elif self.type == 'holiday_name':
            self._state = date.holiday_description
        elif self.type == 'holyness':
            self._state = date.holiday_type
        elif self.type == 'upcoming_shabbat_candle_lighting':
            times = make_zmanim(lagging_date.upcoming_shabbat
                                .previous_day.gdate)
            self._state = times.candle_lighting
        elif self.type == 'upcoming_candle_lighting':
            times = make_zmanim(lagging_date.upcoming_shabbat_or_yom_tov
                                .first_day.previous_day.gdate)
            self._state = times.candle_lighting
        elif self.type == 'upcoming_shabbat_havdalah':
            times = make_zmanim(lagging_date.upcoming_shabbat.gdate)
            self._state = times.havdalah
        elif self.type == 'upcoming_havdalah':
            times = make_zmanim(lagging_date.upcoming_shabbat_or_yom_tov
                                .last_day.gdate)
            self._state = times.havdalah
        elif self.type == 'issur_melacha_in_effect':
            self._state = make_zmanim(now).issur_melacha_in_effect
        else:
            times = make_zmanim(today).zmanim
            self._state = times[self.type].time()

        _LOGGER.debug("New value: %s", self._state)
