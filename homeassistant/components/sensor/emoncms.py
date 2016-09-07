"""
Support for the emoncms suite.

"""
import logging
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import homeassistant.util as util
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_URL, CONF_VALUE_TEMPLATE,
    CONF_UNIT_OF_MEASUREMENT, CONF_ID, CONF_SCAN_INTERVAL)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

DECIMALS = 2
CONF_EXCLUDE_FEEDID = "exclude_feed_id"
CONF_INCLUDE_FEEDID = "include_feed_id"
CONF_INCLUDE_FEEDID_NAMES = "include_feed_id_names"
DEFAULT_SCAN_INTERVAL = 60

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_ID): cv.string,
    vol.Optional(CONF_EXCLUDE_FEEDID, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_INCLUDE_FEEDID, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_INCLUDE_FEEDID_NAMES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="W"): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL):vol.All(vol.Coerce(int), vol.Range(min=5)),

})

# entity attributes
ATTR_SIZE = 'Size'
ATTR_LASTUPDATETIME = 'LastUpdateTime'
ATTR_TAG = 'Tag'
ATTR_FEEDID = 'FeedId'
ATTR_USERID = 'UserID'
ATTR_FEEDNAME = 'FeedName'
ATTR_LASTUPDATETIMESTR = 'LastUpdateTimeStr'

def getId(SensorID, feedtag, feedname, feedid, feeduserid):
    return "emoncms" + SensorID + "_" + feedtag + "_" + \
           feedname + "_" + feedid + "_" + feeduserid

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Emoncms sensor."""

    apikey = config.get(CONF_API_KEY)
    url = config.get(CONF_URL)
    sensorid = config.get(CONF_ID)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    exclude_feeds = config.get(CONF_EXCLUDE_FEEDID)
    include_feeds = config.get(CONF_INCLUDE_FEEDID)
    include_feeds_names = config.get(CONF_INCLUDE_FEEDID_NAMES)
    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)

    data = EmonCmsData(hass, url, apikey, interval)
    data.update(dt_util.utcnow())

    """ fail setup_platform if no data was returned """
    if data.data is None:
        return False
    
    sensors = []
    include_length = len(include_feeds)
    exclude_length = len(exclude_feeds)
    include_names_length = len(include_feeds_names)
    index = 0
    
    for elem in data.data:
        if include_length == 0:
            if exclude_length == 0:
                """Add All feeds"""
                sensors.append(EmonCmsSensor(hass, data, None, value_template, unit_of_measurement, sensorid,
                                             elem["id"], elem["name"], elem["userid"], elem["tag"],
                                             elem["size"], elem["time"], elem["value"]))
            else:
                """Add All feeds except ..."""
                if not elem["id"] in exclude_feeds:
                    sensors.append(EmonCmsSensor(hass, data, None, value_template, unit_of_measurement, sensorid,
                                                 elem["id"], elem["name"], elem["userid"], elem["tag"],
                                                 elem["size"], elem["time"], elem["value"]))
        
        else:
            if exclude_length == 0:
                """Only include these feed id's ..."""
                if elem["id"] in include_feeds:
                    name = None;
                    if include_names_length > 0:
                        if index < include_names_length:
                            name = include_feeds_names[index]
                            index = index + 1
                    sensors.append(EmonCmsSensor(hass, data, name, value_template, unit_of_measurement, sensorid,
                                                 elem["id"], elem["name"], elem["userid"], elem["tag"],
                                                 elem["size"], elem["time"], elem["value"]))
                        
            else:
                _LOGGER.error("Both config values '%s' and '%s' are specified this is not valid! " + \
                              "Please check your configuration",
                              CONF_EXCLUDE_FEEDID, CONF_INCLUDE_FEEDID)
                return
            
    add_devices(sensors)    

      
class EmonCmsSensor(Entity):
    """Implementation of an EmonCmsSensor sensor."""

    def __init__(self, hass, data, name, value_template, unit_of_measurement, sensorid,
                 feedid, feedname, userid, tag, size, lastupdatetime, value):
        """Initialize the sensor."""

        if name is None:
            self._name = "emoncms" + sensorid + "_feedid_" + feedid
        else:
            self._name = name
        self._identifier = getId(sensorid, tag, feedname, feedid, userid)
        self._hass = hass
        self._data = data
        self._feedid = feedid
        self._userid = userid
        self._tag = tag
        self._feedname = feedname
        self._value_template = value_template
        self._size = size
        self._lastupdatetime = lastupdatetime
        self._value = value
        self._unit_of_measurement = unit_of_measurement
        self._sensorid = sensorid
        if self._value_template is not None:
            self._state = template.render_with_possible_json_value(
                self._hass, self._value_template, self._value, "N/A")
        else:
            self._state = round(float(self._value), DECIMALS);
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
    
    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        if self._data is None:
            return

        found = False
        if self._data.data is not None:            
            for elem in self._data.data:
                id = getId(self._sensorid, elem["tag"], elem["name"], elem["id"], elem["userid"])                     
                if id == self._identifier:
                    found = True;
                    self._lastupdatetime = elem["time"]
                    self._size = elem["size"]
                    self._value = elem["value"]
                    break
                
        if found:
            if self._value_template is not None:
                self._state = template.render_with_possible_json_value(
                    self._hass, self._value_template, self._value, "N/A")
            else:
                self._state = round(float(self._value), DECIMALS);
            self.update_ha_state()
        
    @property
    def state_attributes(self):
        """ returns the atrributes of the sensor """
        return {
            ATTR_FEEDID : self._feedid,
            ATTR_TAG : self._tag,
            ATTR_FEEDNAME : self._feedname,
            ATTR_SIZE : self._size,
            ATTR_USERID : self._userid,
            ATTR_LASTUPDATETIME : self._lastupdatetime,
            ATTR_LASTUPDATETIMESTR : template.timestamp_local(float(self._lastupdatetime)),
        }
    
class EmonCmsData(object):
    """The class for handling the data retrieval."""

    def __init__(self, hass, url, apikey, interval):
        """Initialize the data object."""
        self._apikey = apikey        
        self._url = url + "/feed/list.json"
        self._interval = interval                
        self._hass = hass
        self.data = None
            
    def update(self, now):
        """Get the latest data """       
        try:
            try:    
                r = requests.get(self._url, params={"apikey":self._apikey}, verify=False, allow_redirects=True, timeout=5)            
            except requests.exceptions.RequestException as e:
                _LOGGER.error(e)                
                return
                
            if r.status_code == 200:            
                self.data = r.json()                                                    
            else:
                _LOGGER.error("please verify if the specified config value '%s' is correct! (HTTP Status_code = %d)", CONF_URL, r.status_code)             
        finally:
            """ during setup don't schedule new call, however if setup was succesfull (there
                should be already data availible) keep trying since the connection could
                be temporary down (server reboot for example at least in my use case it can happen)"""  
            if not self.data is None:
                track_point_in_utc_time(self._hass, self.update, now + timedelta(seconds=self._interval))
            
      
