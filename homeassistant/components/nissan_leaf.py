import voluptuous as vol
import logging
from datetime import timedelta
import urllib

import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.discovery import load_platform
import asyncio


REQUIREMENTS = ['https://github.com/BenWoodford/pycarwings2/archive/master.zip'
                '#pycarwings']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'nissan_leaf'
DATA_LEAF = 'nissan_leaf_data'

DATA_BATTERY = 'battery'
DATA_LOCATION = 'location'
DATA_CHARGING = 'charging'
DATA_CLIMATE = 'climate'

CONF_INTERVAL = 'update_interval'
DEFAULT_INTERVAL = 30

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

LEAF_COMPONENTS = [
    'sensor', 'switch'#, 'device_tracker',
]

@asyncio.coroutine
def async_setup(hass, config):
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    import pycarwings2

    _LOGGER.debug("Logging into You+Nissan...")

    try:
        s = pycarwings2.Session(username, password, "NE")
        _LOGGER.Info("Fetching Leaf Data")
        leaf = s.get_leaf()
    except(RuntimeError, urllib.error.HTTPError):
        _LOGGER.error("Unable to connect to Nissan Connect with username and password")
        return False
    except(KeyError):
        _LOGGER.error("Unable to fetch car details... do you actually have a Leaf connected to your account?")
        return False
    except:
        _LOGGER.error("An unknown error occurred while connecting to Nissan's servers: " + sys.exc_info()[0])

    _LOGGER.Info("Successfully logged in and fetched Leaf info")
    _LOGGER.Info("WARNING: This component may poll your Leaf too often, and drain the 12V. If you drain your car's 12V it won't start as the drive train battery won't connect, so you have been warned.")

    hass.data[DATA_LEAF] = LeafDataStore(leaf)

    for component in LEAF_COMPONENTS:
        load_platform(hass, component, DOMAIN, {}, config)

    return True

class LeafDataStore:

    def __init__(self, leaf):
        self.leaf = leaf
        self.data = {}

    @Throttle(timedelta(minutes=DEFAULT_INTERVAL))
    def update(self):
        batteryResponse = self.get_battery()
        if batteryResponse.answer == 200:
            self.data[DATA_BATTERY] = 0
            self.data[DATA_CHARGING] = batteryResponse.is_charging

        climateResponse = self.get_climate()
        self.data[DATA_CLIMATE] = climateResponse.is_hvac_running

        locationResponse = self.get_location()
        self.data[DATA_LOCATION] = locationResponse

    def get_battery(self):
        request = self.leaf.request_update()
        battery_status = self.leaf.get_status_from_update(request)
        while battery_status is None:
            time.sleep(5)
            battery_status = self.leaf.get_status_from_update(request)

        _LOGGER.info(battery_status)

        return battery_status

    def get_climate(self):
        return None

    def set_climate(self, toggle):
        if toggle:
            request = self.leaf.start_climate_control()
            climate_result = self.leaf.get_start_climate_control_result(request)
            
            while climate_result is None:
                time.sleep(5)
                climate_result = self.leaf.get_start_climate_control_result(request)

            return climate_result.is_hvac_running
        else:
            request = self.leaf.stop_climate_control()
            climate_result = self.leaf.get_stop_climate_control_result(request)
            
            while climate_result is None:
                time.sleep(5)
                climate_result = self.leaf.get_stop_climate_control_result(request)

            return not climate_result.is_hvac_running

    def get_location(self):
        request = self.left.request_location()
        location_status = self.leaf.get_status_from_location(request)

        while location_status is None:
            time.sleep(5)
            location_status = self.leaf.get_status_from_location(request)
        
        return location_status
    
    def start_charging(self):
        return self.leaf.start_charging()