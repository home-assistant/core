import voluptuous as vol
import logging
from datetime import timedelta
import time
import urllib

import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.entity import Entity
import asyncio
import sys
from homeassistant.helpers.event import track_time_interval
from homeassistant.util.async import fire_coroutine_threadsafe


REQUIREMENTS = ['https://github.com/BenWoodford/pycarwings2/archive/master.zip'
                '#pycarwings']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'nissan_leaf'
DATA_LEAF = 'nissan_leaf_data'

DATA_BATTERY = 'battery'
DATA_LOCATION = 'location'
DATA_CHARGING = 'charging'
DATA_PLUGGED_IN = 'plugged_in'
DATA_CLIMATE = 'climate'
DATA_RANGE_AC = 'range_ac_on'
DATA_RANGE_AC_OFF = 'range_ac_off'

CONF_NCONNECT = 'nissan_connect'
CONF_INTERVAL = 'update_interval'
CONF_REGION = 'region'
CONF_VALID_REGIONS = ['NNA', 'NE', 'NCI', 'NMA', 'NML']
DEFAULT_INTERVAL = 30

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_REGION): vol.In(CONF_VALID_REGIONS),
        vol.Optional(CONF_NCONNECT, default=True): cv.boolean,
        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

LEAF_COMPONENTS = [
    'sensor', 'switch', 'device_tracker',
]

SIGNAL_UPDATE_LEAF = 'nissan_leaf_update'


def setup(hass, config):
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    import pycarwings2

    _LOGGER.debug("Logging into You+Nissan...")

    try:
        s = pycarwings2.Session(
            username, password, config[DOMAIN][CONF_REGION])
        _LOGGER.debug("Fetching Leaf Data")
        leaf = s.get_leaf()
    except(RuntimeError, urllib.error.HTTPError):
        _LOGGER.error(
            "Unable to connect to Nissan Connect with username and password")
        return False
    except(KeyError):
        _LOGGER.error(
            "Unable to fetch car details... do you actually have a Leaf connected to your account?")
        return False
    except:
        _LOGGER.error(
            "An unknown error occurred while connecting to Nissan's servers: ", sys.exc_info()[0])

    _LOGGER.info("Successfully logged in and fetched Leaf info")
    _LOGGER.info("WARNING: This component may poll your Leaf too often, and drain the 12V. If you drain your car's 12V it won't start as the drive train battery won't connect, so you have been warned.")

    hass.data[DATA_LEAF] = {}
    hass.data[DATA_LEAF][leaf.vin] = LeafDataStore(
        leaf, hass, config)

    for component in LEAF_COMPONENTS:
        if (component != 'device_tracker') or (config[DOMAIN][CONF_NCONNECT] == True):
            load_platform(hass, component, DOMAIN, {}, config)

    hass.data[DATA_LEAF][leaf.vin].refresh_leaf_if_necessary(0)

    return True


class LeafDataStore:

    def __init__(self, leaf, hass, config):
        self.leaf = leaf
        self.config = config
        self.nissan_connect = config[DOMAIN][CONF_NCONNECT]
        self.hass = hass
        self.data = {}
        self.data[DATA_CLIMATE] = False
        self.data[DATA_BATTERY] = 1
        self.data[DATA_CHARGING] = False
        self.data[DATA_LOCATION] = False
        track_time_interval(
            hass, self.refresh_leaf_if_necessary, timedelta(minutes=config[DOMAIN][CONF_INTERVAL]))

    def refresh_leaf_if_necessary(self, event_time):
        _LOGGER.debug("Interval fired, refreshing data...")
        self.refresh_data()

    def refresh_data(self):
        _LOGGER.debug("Updating Nissan Leaf Data")

        batteryResponse = self.get_battery()
        _LOGGER.debug("Got battery data for Leaf")

        if batteryResponse.answer['status'] == 200:
            self.data[DATA_BATTERY] = batteryResponse.battery_percent
            self.data[DATA_CHARGING] = batteryResponse.is_charging
            self.data[DATA_PLUGGED_IN] = batteryResponse.is_connected
            self.data[DATA_RANGE_AC] = batteryResponse.cruising_range_ac_on_km
            self.data[DATA_RANGE_AC_OFF] = batteryResponse.cruising_range_ac_off_km

        _LOGGER.debug("Battery Response: ")
        _LOGGER.debug(batteryResponse.__dict__)

        climateResponse = self.get_climate()

        if climateResponse is not None:
            _LOGGER.debug("Got climate data for Leaf")
            _LOGGER.debug(climateResponse.__dict__)
            self.data[DATA_CLIMATE] = climateResponse.is_hvac_running

        if self.nissan_connect:
            try:
                locationResponse = self.get_location()

                if locationResponse is None:
                    _LOGGER.debug("Empty Location Response Received")
                    self.data[DATA_LOCATION] = None
                else:
                    LOGGER.debug("Got location data for Leaf")
                    self.data[DATA_LOCATION] = locationResponse

                    _LOGGER.debug("Location Response: ")
                    _LOGGER.debug(locationResponse.__dict__)
            except Exception as e:
                _LOGGER.error("Error fetching location info")

        _LOGGER.debug("Notifying Components")
        dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)

    def get_battery(self):
        request = self.leaf.request_update()
        battery_status = self.leaf.get_status_from_update(request)
        while battery_status is None:
            _LOGGER.debug("Battery data not in yet.")
            time.sleep(5)
            battery_status = self.leaf.get_status_from_update(request)

        return battery_status

    def get_climate(self):
        request = self.leaf.get_latest_hvac_status()
        return request

    def set_climate(self, toggle):
        if toggle:
            request = self.leaf.start_climate_control()
            climate_result = self.leaf.get_start_climate_control_result(
                request)

            while climate_result is None:
                _LOGGER.debug("Climate data not in yet.")
                time.sleep(5)
                climate_result = self.leaf.get_start_climate_control_result(
                    request)

            return climate_result.is_hvac_running
        else:
            request = self.leaf.stop_climate_control()
            climate_result = self.leaf.get_stop_climate_control_result(request)

            while climate_result is None:
                _LOGGER.debug("Climate data not in yet.")
                time.sleep(5)
                climate_result = self.leaf.get_stop_climate_control_result(
                    request)

            return climate_result.is_hvac_running

    def get_location(self):
        request = self.leaf.request_location()
        location_status = self.leaf.get_status_from_location(request)

        while location_status is None:
            _LOGGER.debug("Location data not in yet.")
            time.sleep(5)
            location_status = self.leaf.get_status_from_location(request)

        return location_status

    def start_charging(self):
        return self.leaf.start_charging()


class LeafEntity(Entity):
    def __init__(self, car):
        self.car = car

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.log_registration()
        async_dispatcher_connect(
            self.car.hass, SIGNAL_UPDATE_LEAF, self._update_callback)

    def _update_callback(self):
        """Callback update method."""
        #_LOGGER.debug("Got dispatcher update from Leaf platform")
        self.schedule_update_ha_state(True)
