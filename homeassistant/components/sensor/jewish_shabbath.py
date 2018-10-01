import logging
import urllib
import json
import datetime
import time
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_SCAN_INTERVAL, CONF_RESOURCES)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=60)
SENSOR_PREFIX = 'Shabbat '
GEOID = 'geoid'
HAVDALAH_MINUTES = 'havdalah_calc'
TIME_BEFORE_CHECK = 'time_before_check'
TIME_AFTER_CHECK = 'time_after_check'
LATITUDE = 'latitude'
LONGITUDE = 'longitude'

SENSOR_TYPES = {
    'in': ['כניסת שבת', 'mdi:candle', 'in'],
    'out': ['צאת שבת', 'mdi:exit-to-app', 'out'],
    'is_shabbat': ['IN', 'mdi:candle', 'is_shabbat'],
    'parasha': ['פרשת השבוע', 'mdi:book-open-variant', 'parasha'],
    'hebrew_date': ['תאריך עברי', 'mdi:calendar', 'hebrew_date'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(GEOID): cv.string,
    vol.Required(LONGITUDE): cv.string,
    vol.Required(GEOID): cv.string,
    vol.Optional(HAVDALAH_MINUTES, default=42): int,
    vol.Optional(TIME_BEFORE_CHECK, default=10): int,
    vol.Optional(TIME_AFTER_CHECK, default=10): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    vol.Required(CONF_RESOURCES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the shabbat config sensors."""
    havdalah = config.get(HAVDALAH_MINUTES)
    geoid = config.get(GEOID)
    latitude = config.get(LATITUDE)
    longitude = config.get(LONGITUDE)
    time_before = config.get(TIME_BEFORE_CHECK)
    time_after = config.get(TIME_AFTER_CHECK)
    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        if sensor_type not in SENSOR_TYPES:
            SENSOR_TYPES[sensor_type] = [
                sensor_type.title(), '', 'mdi:flash']

        entities.append(Shabbat(sensor_type, geoid, latitude, longitude,
                                havdalah, time_before, time_after))

    add_entities(entities)


# pylint: disable=abstract-method

class Shabbat(Entity):
    """Representation of a shabbat and hagg."""
    shabbat_db = None
    hebrew_date_db = None
    shabbatin = None
    shabbatout = None
    datetoday = datetime.date.today()
    fulltoday = datetime.datetime.today()
    friday = None
    saturday = None

    def __init__(self, sensor_type, geoid, latitude, longitude, havdalah, time_before, time_after):
        """Initialize the sensor."""
        self.type = sensor_type
        self._geoid = geoid
        self._latitude = latitude
        self._longitude = longitude
        self._havdalah = havdalah
        self._time_before = time_before
        self._time_after = time_after
        self._name = SENSOR_PREFIX + SENSOR_TYPES[self.type][2]
        self._friendly_name = SENSOR_TYPES[self.type][0]
        self._icon = SENSOR_TYPES[self.type][1]
        self._state = None
        self.update_db()
        self.get_full_time_in()
        self.get_full_time_out()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def friendly_name(self):
        """Return the name of the sensor."""
        return self._friendly_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """update our sensor state."""
        self.datetoday = datetime.date.today()
        self.fulltoday = datetime.datetime.today()
        if self.type.__eq__('in'):
            self._state = self.get_time_in()
        elif self.type.__eq__('out'):
            self._state = self.get_time_out()
        elif self.type.__eq__('is_shabbat'):
            self._state = self.is_shabbat()
        elif self.type.__eq__('parasha'):
            self._state = self.get_parasha()
        elif self.type.__eq__('hebrew_date'):
            self._state = self.get_hebrew_date()

    @Throttle(datetime.timedelta(minutes=5))
    def update_db(self):
        self.set_days()
        with urllib.request.urlopen(
            "https://www.hebcal.com/hebcal/?v=1&cfg=fc&start="
            + str(self.friday) + "&end=" + str(self.saturday)
            + "&ss=on&c=on&geo=geoname&geonameid=" + str(self._geoid)
            + "&m=" + str(self._havdalah) + "&s=on"
        ) as url:
            self.shabbat_db = json.loads(url.read().decode())
        with urllib.request.urlopen(
            "https://www.hebcal.com/converter/?cfg=json&gy="
            + str(self.datetoday.year) + "&gm=" + str(self.datetoday.month)
            + "&gd=" + str(self.datetoday.day) + "&g2h=1"
        ) as heb_url:
            self.hebrew_date_db = json.loads(heb_url.read().decode())
        self.get_full_time_in()
        self.get_full_time_out()

    def set_days(self):
        weekday = self.set_friday(datetime.date.today().isoweekday())
        self.friday = datetime.date.today()+datetime.timedelta(days=weekday)
        self.saturday = datetime.date.today()+datetime.timedelta(days=weekday+1)

    def set_friday(self, day):
        switcher = {
            7: 5,
            1: 5,
            2: 4,
            3: 3,
            4: 2,
            5: 0,
            6: -1,
        }
        return switcher.get(day)

    # get shabbat entrace
    def get_time_in(self):
        result = ''
        for extract_data in self.shabbat_db:
            if extract_data['className'] == "candles":
                result = extract_data['start'][11:16]
        if self.is_time_format(result):
            return result
        return 'Error'

    # get shabbat time exit
    def get_time_out(self):
        result = ''
        for extract_data in self.shabbat_db:
            if extract_data['className'] == "havdalah":
                result = extract_data['start'][11:16]
        if self.is_time_format(result):
            return result
        return 'Error'

    # get full time entrace shabbat for check if is shabbat now
    def get_full_time_in(self):
        for extract_data in self.shabbat_db:
            if extract_data['className'] == "candles":
                self.shabbatin = extract_data['start']
        if self.shabbatin is not None:
            self.shabbatin = self.shabbatin[:22]+'00'

    # get full time exit shabbat for check if is shabbat now
    def get_full_time_out(self):
        for extract_data in self.shabbat_db:
            if extract_data['className'] == "havdalah":
                self.shabbatout = extract_data['start']
        if self.shabbatout is not None:
            self.shabbatout = self.shabbatout[:22]+'00'

    # get parashat hashavo'h
    def get_parasha(self):
        result = 'שבת מיוחדת'
        get_shabbat_name = None
        for extract_data in self.shabbat_db:
            if extract_data['className'] == "parashat":
                result = extract_data['hebrew']
            for data in extract_data.keys():
                if data == 'subcat' and extract_data[data] == 'shabbat':
                    get_shabbat_name = extract_data
        if get_shabbat_name is not None:
            result = result+' - '+get_shabbat_name['hebrew']
        return result

    # check if is shabbat now / return true or false
    def is_shabbat(self):
        if self.shabbatin is not None and self.shabbatout is not None:
            is_in = datetime.datetime.strptime(self.shabbatin, '%Y-%m-%dT%H:%M:%S%z')
            is_out = datetime.datetime.strptime(self.shabbatout, '%Y-%m-%dT%H:%M:%S%z')
            is_in = is_in - datetime.timedelta(minutes=int(self._time_before))
            is_out = is_out + datetime.timedelta(minutes=int(self._time_after))
            if is_in.replace(tzinfo=None) < self.fulltoday < is_out.replace(tzinfo=None):
                return 'True'
            else:
                return 'False'
        else:
            return 'False'

    # convert to hebrew date
    def get_hebrew_date(self):
        return self.hebrew_date_db['hebrew']

    # check if the time is correct
    def is_time_format(self, input):
        try:
            time.strptime(input, '%H:%M')
            return True
        except ValueError:
            return False
