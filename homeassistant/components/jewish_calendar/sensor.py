"""Platform to retrieve Jewish calendar information for Home Assistant."""
import logging

import hdate

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, SUN_EVENT_SUNSET
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
        JewishCalendarTimeSensor(hass.data[DOMAIN], sensor, sensor_info)
        for sensor, sensor_info in SENSOR_TYPES["time"].items()
    )

    async_add_entities(sensors)


class JewishCalendarSensor(SensorEntity):
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
        self._prefix = data["prefix"]
        self._holiday_attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Generate a unique id."""
        return f"{self._prefix}_{self._type}"

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
        _LOGGER.debug("Now: %s Location: %r", now, self._location)

        today = now.date()
        sunset = dt_util.as_local(
            get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)
        )

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        daytime_date = hdate.HDate(today, diaspora=self._diaspora, hebrew=self._hebrew)

        # The Jewish day starts after darkness (called "tzais") and finishes at
        # sunset ("shkia"). The time in between is a gray area (aka "Bein
        # Hashmashot" - literally: "in between the sun and the moon").

        # For some sensors, it is more interesting to consider the date to be
        # tomorrow based on sunset ("shkia"), for others based on "tzais".
        # Hence the following variables.
        after_tzais_date = after_shkia_date = daytime_date
        today_times = self.make_zmanim(today)

        if now > sunset:
            after_shkia_date = daytime_date.next_day

        if today_times.havdalah and now > today_times.havdalah:
            after_tzais_date = daytime_date.next_day

        self._state = self.get_state(daytime_date, after_shkia_date, after_tzais_date)
        _LOGGER.debug("New value for %s: %s", self._type, self._state)

    def make_zmanim(self, date):
        """Create a Zmanim object."""
        return hdate.Zmanim(
            date=date,
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            hebrew=self._hebrew,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._type != "holiday":
            return {}
        return self._holiday_attrs

    def get_state(self, daytime_date, after_shkia_date, after_tzais_date):
        """For a given type of sensor, return the state."""
        # Terminology note: by convention in py-libhdate library, "upcoming"
        # refers to "current" or "upcoming" dates.
        if self._type == "date":
            return after_shkia_date.hebrew_date
        if self._type == "weekly_portion":
            # Compute the weekly portion based on the upcoming shabbat.
            return after_tzais_date.upcoming_shabbat.parasha
        if self._type == "holiday":
            self._holiday_attrs["id"] = after_shkia_date.holiday_name
            self._holiday_attrs["type"] = after_shkia_date.holiday_type.name
            self._holiday_attrs["type_id"] = after_shkia_date.holiday_type.value
            return after_shkia_date.holiday_description
        if self._type == "omer_count":
            return after_shkia_date.omer_day
        if self._type == "daf_yomi":
            return daytime_date.daf_yomi

        return None


class JewishCalendarTimeSensor(JewishCalendarSensor):
    """Implement attrbutes for sensors returning times."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return dt_util.as_utc(self._state) if self._state is not None else None

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        if self._state is None:
            return attrs

        return attrs

    def get_state(self, daytime_date, after_shkia_date, after_tzais_date):
        """For a given type of sensor, return the state."""
        if self._type == "upcoming_shabbat_candle_lighting":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat.previous_day.gdate
            )
            return times.candle_lighting
        if self._type == "upcoming_candle_lighting":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
            )
            return times.candle_lighting
        if self._type == "upcoming_shabbat_havdalah":
            times = self.make_zmanim(after_tzais_date.upcoming_shabbat.gdate)
            return times.havdalah
        if self._type == "upcoming_havdalah":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.last_day.gdate
            )
            return times.havdalah

        times = self.make_zmanim(dt_util.now()).zmanim
        return times[self._type]
