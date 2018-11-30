"""
Support for Rova garbage calendar.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rova/
"""

import asyncio
from datetime import datetime, timedelta
import json
import logging
import random
from string import Template

import requests

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

DOMAIN = "rova"

# Config for rova requests.
CONF_ZIPCODE = "zip_code"
CONF_HOUSENUMBER = "house_number"

_LOGGER = logging.getLogger(__name__)

# Possible garbage types to process.
garbageTypeMappings = {'gft':'gft', 
        'papier':'papier', 
        'plasticplus':'pmd', 
        'rest':'rest'}

# Request parameters will be set during setup.
url = 'https://www.rova.nl/api/TrashCalendar/GetCalendarItems'
params = {'portal': 'inwoners'}
cookies_template = Template("{'Id':${rovaid},'ZipCode':'${zipcode}',
        'HouseNumber':'${housenumber}','HouseAddition':'','Municipality':'',
        'Province':'','Firstname':'','Lastname':'','UserAgent':'',
        'School':'','Street':'','Country':'','Portal':'',
        'Lat':'','Lng':'','AreaLevel':'','City':'','Ip':''}")
cookies = {};

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, 
        discovery_info=None):
    
    # Create rova data service which will retrieve and update the data.
    data = RovaData(hass)
   
    # Create a new sensor for each garbage type.
    entities = []
    for garbageTypeCode in garbageTypeMappings:
        sensor = RovaSensor(garbageTypeCode, data)
        entities.append(sensor)

    async_add_entities(entities, True)

    rovaId = random.randint(10000, 30000)
    zipCode = config.get(CONF_ZIPCODE, None)
    houseNumber = config.get(CONF_HOUSENUMBER, None)

    if None in (zipCode, houseNumber):
       _LOGGER.error("Zip code or house number not set in 
               Home Assistant config")
       return False
    
    # Set cookies based on config and template, only id, zip code 
    # and house number need to be set.
    cookies['RovaLc_inwoners'] = cookies_template.substitute(rovaid=rovaId, 
            zipcode=zipCode, housenumber=houseNumber)

    # Schedule first data service update straight away.
    async_track_point_in_utc_time(hass, data.async_update, dt_util.utcnow())

class RovaSensor(Entity):
    
    def __init__(self, garbageTypeCode, data):
        self.code = garbageTypeCode
        self.data = data

    @property
    def name(self):
        return 'rova_garbage_' + garbageTypeMappings[self.code]

    @property
    def state(self):
        if self.code in self.data.data:
            return self.data.data.get(self.code).isoformat()
        else:
            return 0

class RovaData:

    def __init__(self, hass):
        self.hass = hass
        self.data = {}

    @asyncio.coroutine
    def schedule_update(self):
        nxt = dt_util.utcnow() + timedelta(days=1)
        _LOGGER.debug("Scheduling next Rova update in 1 day")
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)
    
    @asyncio.coroutine
    def async_update(self, *_):

        response = requests.get(url, params=params, cookies=cookies)
        calendar = json.loads(response.text)
        
        _LOGGER.debug(calendar)

        self.data = {}
        
        for item in calendar:
            date = datetime.strptime(item['Date'], '%Y-%m-%dT%H:%M:%S')
            code = item['GarbageTypeCode'].lower()
            
            if code not in self.data and date > datetime.now():
                self.data[code] = date
        
        _LOGGER.debug("Updated Rova calendar: %s", self.data)

        yield from self.schedule_update()
        return
