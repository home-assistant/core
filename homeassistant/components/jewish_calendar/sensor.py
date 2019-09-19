"""Platform to retrieve Jewish calendar information for Home Assistant."""
import logging

import hdate

from homeassistant.const import SUN_EVENT_SUNSET
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import get_astral_event_date
import homeassistant.util.dt as dt_util

from . import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Jewish calendar sensor platform."""
    if discovery_info is None:
        return

    sensors = [
        JewishCalendarSensor(hass.data[DOMAIN], sensor, sensor_info)
        for sensor, sensor_info in SENSOR_TYPES["data"].items()
    ]
    sensors.extend(
        JewishCalendarSensor(hass.data[DOMAIN], sensor, sensor_info)
        for sensor, sensor_info in SENSOR_TYPES["time"].items()
    )

    async_add_entities(sensors)


class JewishCalendarSensor(Entity):
    """Representation of an Jewish calendar sensor."""

    def __init__(self, data, sensor, sensor_info):
        """Initialize the Jewish calendar sensor."""
        self._location = data["location"]
        self._type = sensor
        self._name = f"{data['name']} {sensor_info[0]}"
        self._icon = sensor_info[1]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._diaspora = data["diaspora"]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to display in the front end."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update the state of the sensor."""
        now = dt_util.now()
        _LOGGER.debug("Now: %s Timezone = %s", now, now.tzinfo)

        today = now.date()
        sunset = dt_util.as_local(
            get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)
        )

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        def make_zmanim(date):
            """Create a Zmanim object."""
            return hdate.Zmanim(
                date=date,
                location=self._location,
                candle_lighting_offset=self._candle_lighting_offset,
                havdalah_offset=self._havdalah_offset,
                hebrew=self._hebrew,
            )

        date = hdate.HDate(today, diaspora=self._diaspora, hebrew=self._hebrew)

        # The Jewish day starts after darkness (called "tzais") and finishes at
        # sunset ("shkia"). The time in between is a gray area (aka "Bein
        # Hashmashot" - literally: "in between the sun and the moon").

        # For some sensors, it is more interesting to consider the date to be
        # tomorrow based on sunset ("shkia"), for others based on "tzais".
        # Hence the following variables.
        after_tzais_date = after_shkia_date = date
        today_times = make_zmanim(today)

        if now > sunset:
            after_shkia_date = date.next_day

        if today_times.havdalah and now > today_times.havdalah:
            after_tzais_date = date.next_day

        # Terminology note: by convention in py-libhdate library, "upcoming"
        # refers to "current" or "upcoming" dates.
        if self._type == "date":
            self._state = after_shkia_date.hebrew_date
        elif self._type == "weekly_portion":
            # Compute the weekly portion based on the upcoming shabbat.
            self._state = after_tzais_date.upcoming_shabbat.parasha
        elif self._type == "holiday_name":
            self._state = after_shkia_date.holiday_description
        elif self._type == "holiday_type":
            self._state = after_shkia_date.holiday_type
        elif self._type == "upcoming_shabbat_candle_lighting":
            times = make_zmanim(after_tzais_date.upcoming_shabbat.previous_day.gdate)
            self._state = times.candle_lighting
        elif self._type == "upcoming_candle_lighting":
            times = make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
            )
            self._state = times.candle_lighting
        elif self._type == "upcoming_shabbat_havdalah":
            times = make_zmanim(after_tzais_date.upcoming_shabbat.gdate)
            self._state = times.havdalah
        elif self._type == "upcoming_havdalah":
            times = make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.last_day.gdate
            )
            self._state = times.havdalah
        elif self._type == "omer_count":
            self._state = after_shkia_date.omer_day
        else:
            times = make_zmanim(today).zmanim
            self._state = times[self._type].time()

        _LOGGER.debug("New value: %s", self._state)
