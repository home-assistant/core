"""
Support for SolarEdge Monitoring API

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solaredge/
"""

import asyncio
from datetime import datetime, timedelta
import json
import logging

import requests

from homeassistant.const import CONF_MONITORED_VARIABLES
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

DOMAIN = "solaredge"

# Config for solaredge monitoring api requests.
CONF_APIKEY = "api_key"
CONF_SITEID = "site_id"

DELAY_OK = 10
DELAY_NOT_OKAY = 20

# Supported sensor types:
# Key: ['name', unit, icon]
SENSOR_TYPES = {
  'lifeTimeData': ["Lifetime energy", 'Wh', 'mdi:solar-power'],
  'lastYearData': ["Energy this year", 'Wh', 'mdi:solar-power'],
  'lastMonthData' : ["Energy this month", 'Wh', 'mdi:solar-power'],
  'lastDayData' : ["Energy today", 'Wh', 'mdi:solar-power'],
  'currentPower' : ["Current Power", 'W', 'mdi:solar-power']
}

_LOGGER = logging.getLogger(__name__)

# Request parameters will be set during platform setup.
url = 'https://monitoringapi.solaredge.com/site/{siteId}/overview'
params = {}

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, 
        discovery_info=None):
    global url, params

    apiKey = config.get(CONF_APIKEY, None)
    siteId = config.get(CONF_SITEID, None)

    if None in (apiKey, siteId):
       _LOGGER.error("api_key or site_id not set in Home Assistant config")
       return False

    # Setup request url and parameters.
    url = url.format(siteId=siteId)
    params['api_key'] = apiKey
    
    # Create solaredge data service which will retrieve and update the data.
    data = SolarEdgeData(hass)
   
    # Create a new sensor for each sensor type.
    entities = []
    for sensorType in config[CONF_MONITORED_VARIABLES]:
        sensor = SolarEdgeSensor(sensorType, data)
        entities.append(sensor)

    async_add_entities(entities, True)

    # Schedule first data service update straight away.
    async_track_point_in_utc_time(hass, data.async_update, dt_util.utcnow())

class SolarEdgeSensor(Entity):
    
    def __init__(self, sensorType, data):
        self.type = sensorType
        self.data = data

        self._name = SENSOR_TYPES[self.type][0]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        return 'solaredge_' + self.type
    
    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def icon(self):
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        if self.type in self.data.data:
            return self.data.data.get(self.type)
        else:
            return 0

class SolarEdgeData:

    def __init__(self, hass):
        self.hass = hass
        self.data = {}

    @asyncio.coroutine
    def schedule_update(self, minutes):
        nxt = dt_util.utcnow() + timedelta(minutes=minutes)
        _LOGGER.debug("Scheduling next SolarEdge update in %s minutes",
                minutes)
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)
    
    @asyncio.coroutine
    def async_update(self, *_):

        response = requests.get(url, params=params)
        
        if response.status_code != requests.codes.ok:
            _LOGGER.debug("failed to retrieve data from SolarEdge API, 
                    delaying next update")
            yield from self.schedule_update(DELAY_NOT_OK)
            return

        data = json.loads(response.text)
        
        if 'overview' not in data:
            _LOGGER.debug("Missing overview data, delaying next update")
            yield from self.schedule_update(DELAY_NOT_OK)
            return

        overview = data['overview']

        self.data = {}
        
        for item in overview:
            value = overview[item]
            if 'energy' in value:
              self.data[item] = value['energy']
            elif 'power' in value:
              self.data[item] = value['power']
        
        _LOGGER.debug("Updated SolarEdge overview data: %s", self.data)

        yield from self.schedule_update(DELAY_OK)
        return
