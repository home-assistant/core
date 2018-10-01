import logging
import urllib
import json
import datetime
import pytz
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

        entities.append(Shabbat_Hagg(sensor_type, geoid, latitude, longitude, havdalah, time_before, time_after))

    add_entities(entities)


# pylint: disable=abstract-method

class Shabbat_Hagg(Entity):
    """Representation of a shabbat and hagg."""
    shabbatDB = None
    hebrew_dateDB = None
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
        self.updateDB()
        self.getFullTimeIn()
        self.getFullTimeOut()

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
            self._state = self.getTimeIn()
        elif self.type.__eq__('out'):
            self._state = self.getTimeOut()
        elif self.type.__eq__('is_shabbat'):
            self._state = self.isShabbat()
        elif self.type.__eq__('parasha'):
            self._state = self.getParasha()
        elif self.type.__eq__('hebrew_date'):
            self._state = self.getHebrewDate()
                
    @Throttle(datetime.timedelta(minutes=5))
    def updateDB(self):
        self.set_days()
        with urllib.request.urlopen(
                "https://www.hebcal.com/hebcal/?v=1&cfg=fc&start=" + str(self.friday) + "&end=" + str(self.saturday) + "&ss=on&c=on&geo=geoname&geonameid="+ str(self._geoid) + "&m=" + str(self._havdalah) + "&s=on") as url:
            self.shabbatDB = json.loads(url.read().decode())
        with urllib.request.urlopen(
                    "https://www.hebcal.com/converter/?cfg=json&gy=" + str(self.datetoday.year) + "&gm=" + str(
                        self.datetoday.month) + "&gd=" + str(self.datetoday.day) + "&g2h=1") as heb_url:
                self.hebrew_dateDB = json.loads(heb_url.read().decode())
        self.getFullTimeIn()
        self.getFullTimeOut()
     
    # set friday and saturday    
    def set_days(self):
        weekday = self.set_friday(datetime.date.today().isoweekday())
        self.friday = datetime.date.today()+datetime.timedelta(days=weekday)
        self.saturday = datetime.date.today()+datetime.timedelta(days=weekday+1)
        
    # get distantce days
    def set_friday(self,day):
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
    def getTimeIn(self):
        result = ''
        for extractData in self.shabbatDB:
            if extractData['className'] == "candles":
                result = extractData['start'][11:16]
        if self.isTimeFormat(result):
            return result
        return 'Error'
        
    # get shabbat time exit
    def getTimeOut(self):
        result = ''
        for extractData in self.shabbatDB:
            if extractData['className'] == "havdalah":
                result = extractData['start'][11:16]
        if self.isTimeFormat(result):
            return result
        return 'Error'
        
    # get full time entrace shabbat for check if is shabbat now
    def getFullTimeIn(self):
        for extractData in self.shabbatDB:
            if extractData['className'] == "candles":
                self.shabbatin = extractData['start']
        if self.shabbatin != None:
            self.shabbatin = self.shabbatin[:22]+'00' 
                
    # get full time exit shabbat for check if is shabbat now
    def getFullTimeOut(self):
        for extractData in self.shabbatDB:
            if extractData['className'] == "havdalah":
                self.shabbatout = extractData['start']
        if self.shabbatout != None:
            self.shabbatout = self.shabbatout[:22]+'00'

    # get parashat hashavo'h
    def getParasha(self):
        result = 'שבת מיוחדת'
        get_shabbat_name = None
        for extractData in self.shabbatDB:
            if extractData['className'] == "parashat":
                result = extractData['hebrew']
            for x in extractData.keys():
                if x == 'subcat' and extractData[x] == 'shabbat':
                    get_shabbat_name = extractData
        if get_shabbat_name is not None:
            result = result+' - '+get_shabbat_name['hebrew']
        return result

    # check if is shabbat now / return true or false
    def isShabbat(self):
        if self.shabbatin != None and self.shabbatout != None:
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
    def getHebrewDate(self):
        return self.hebrew_dateDB['hebrew']
    
    # check if the time is correct
    def isTimeFormat(self,input):
        try:
            time.strptime(input, '%H:%M')
            return True
        except ValueError:
            return False
