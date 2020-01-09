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
        JewishCalendarTimeSensor(hass.data[DOMAIN], sensor, sensor_info)
        for sensor, sensor_info in SENSOR_TYPES["time"].items()
    )

    async_add_entities(sensors)

# Define fixed values:
DAF_YOMI_CYCLE_11_START = dt_util.dt.date(1997, 9, 29)
DAF_YOMI_MESECHTOS = [
    {"en_name":"Berachos", "heb_name":"ברכות", "pages":63},
    {"en_name":"Shabbos", "heb_name":"שבת", "pages":156},
    {"en_name":"Eruvin", "heb_name":"עירובין", "pages":104},
    {"en_name":"Pesachim", "heb_name":"פסחים", "pages":120},
    {"en_name":"Shekalim", "heb_name":"שקלים", "pages":21},
    {"en_name":"Yoma", "heb_name":"יומא", "pages":87},
    {"en_name":"Succah", "heb_name":"סוכה", "pages":55},
    {"en_name":"Beitzah", "heb_name":"ביצה", "pages":39},
    {"en_name":"Rosh Hashanah", "heb_name":"ראש השנה", "pages":34},
    {"en_name":"Taanis", "heb_name":"תענית", "pages":30},
    {"en_name":"Megillah", "heb_name":"מגילה", "pages":31},
    {"en_name":"Moed Katan", "heb_name":"מועד קטן", "pages":28},
    {"en_name":"Chagigah", "heb_name":"חגיגה", "pages":26},
    {"en_name":"Yevamos", "heb_name":"יבמות", "pages":121},
    {"en_name":"Kesubos", "heb_name":"כתובות", "pages":111},
    {"en_name":"Nedarim", "heb_name":"נדרים", "pages":90},
    {"en_name":"Nazir", "heb_name":"נזיר", "pages":65},
    {"en_name":"Sotah", "heb_name":"סוטה", "pages":48},
    {"en_name":"Gittin", "heb_name":"גיטין", "pages":89},
    {"en_name":"Kiddushin", "heb_name":"קידושין", "pages":81},
    {"en_name":"Bava Kamma", "heb_name":"בבא קמא", "pages":118},
    {"en_name":"Bava Metzia", "heb_name":"בבא מציעא", "pages":118},
    {"en_name":"Bava Basra", "heb_name":"בבא בתרא", "pages":175},
    {"en_name":"Sanhedrin", "heb_name":"סנהדרין", "pages":112},
    {"en_name":"Makkos", "heb_name":"מכות", "pages":23},
    {"en_name":"Shevuos", "heb_name":"שבועות", "pages":48},
    {"en_name":"Avodah Zarah", "heb_name":"עבודה זרה", "pages":75},
    {"en_name":"Horayos", "heb_name":"הוריות", "pages":13},
    {"en_name":"Zevachim", "heb_name":"זבחים", "pages":119},
    {"en_name":"Menachos", "heb_name":"מנחות", "pages":109},
    {"en_name":"Chullin", "heb_name":"חולין", "pages":141},
    {"en_name":"Bechoros", "heb_name":"בכורות", "pages":60},
    {"en_name":"Arachin", "heb_name":"ערכין", "pages":33},
    {"en_name":"Temurah", "heb_name":"תמורה", "pages":33},
    {"en_name":"Kereisos", "heb_name":"כריתות", "pages":27},
    {"en_name":"Meilah", "heb_name":"מעילה", "pages":36},
    {"en_name":"Niddah", "heb_name":"נדה", "pages":72}
    ]

DAF_YOMI_TOTAL_PAGES = sum(mesechta['pages'] for mesechta in DAF_YOMI_MESECHTOS)

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
        self._holiday_attrs = {}

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
        _LOGGER.debug("Now: %s Location: %r", now, self._location)

        today = now.date()
        sunset = dt_util.as_local(
            get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)
        )

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        date = hdate.HDate(today, diaspora=self._diaspora, hebrew=self._hebrew)

        # The Jewish day starts after darkness (called "tzais") and finishes at
        # sunset ("shkia"). The time in between is a gray area (aka "Bein
        # Hashmashot" - literally: "in between the sun and the moon").

        # For some sensors, it is more interesting to consider the date to be
        # tomorrow based on sunset ("shkia"), for others based on "tzais".
        # Hence the following variables.
        after_tzais_date = after_shkia_date = date
        today_times = self.make_zmanim(today)

        if now > sunset:
            after_shkia_date = date.next_day

        if today_times.havdalah and now > today_times.havdalah:
            after_tzais_date = date.next_day

        self._state = self.get_state(after_shkia_date, after_tzais_date)
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
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._type == "holiday":
            return self._holiday_attrs

        return {}

    def get_daf(self, date):
        # The first few cycles were only 2702 blatt. After that it became 2711. Even with
        # that, the math doesn't play nicely with the dates before the 11th cycle :(
        # From Cycle 11 onwards, it was simple and sequential
        days_since_start_cycle_11 = (date - DAF_YOMI_CYCLE_11_START).days
        daf_number = days_since_start_cycle_11 % (DAF_YOMI_TOTAL_PAGES)

        for entry in DAF_YOMI_MESECHTOS:
            if daf_number >= entry["pages"]:
                daf_number -= entry["pages"]
            else:
                if self._hebrew:
                    heb_number = hdate.date.hebrew_number(daf_number + 2)
                    heb_number = heb_number.replace("'", "").replace('"', '')
                    return "%s %s" % (entry["heb_name"], heb_number)
                else:
                    return "%s %s" % (entry["en_name"], daf_number + 2)

    def get_state(self, after_shkia_date, after_tzais_date):
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
            return self.get_daf(dt_util.now().date())

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
        return "timestamp"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        if self._state is None:
            return attrs

        attrs["timestamp"] = self._state.timestamp()

        return attrs

    def get_state(self, after_shkia_date, after_tzais_date):
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
