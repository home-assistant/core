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
DATA_CLIMATE = 'climate'

CONF_NCONNECT = 'nissan_connect'
CONF_INTERVAL = 'update_interval'
DEFAULT_INTERVAL = timedelta(minutes=30)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
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
        s = pycarwings2.Session(username, password, "NE")
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
        leaf, hass, config[DOMAIN][CONF_NCONNECT])

    for component in LEAF_COMPONENTS:
        if (component != 'device_tracker') or (config[DOMAIN][CONF_NCONNECT] == True):
            load_platform(hass, component, DOMAIN, {}, config)

    def refresh_leaf_if_necessary(event_time):
        _LOGGER.debug("Interval fired, refreshing data...")
        fire_coroutine_threadsafe(
            hass.data[DATA_LEAF][leaf.vin].async_update_leaf(), hass.loop)

    track_time_interval(
        hass, refresh_leaf_if_necessary, DEFAULT_INTERVAL)

    refresh_leaf_if_necessary(0)

    return True


class LeafDataStore:

    def __init__(self, leaf, hass, use_nissan_connect):
        self.leaf = leaf
        self.nissan_connect = use_nissan_connect
        self.hass = hass
        self.data = {}
        self.data[DATA_CLIMATE] = False
        self.data[DATA_BATTERY] = 0
        self.data[DATA_CHARGING] = False
        self.data[DATA_LOCATION] = False

    @asyncio.coroutine
    def async_update_leaf(self):
        _LOGGER.debug("Updating Nissan Leaf Data")

        batteryResponse = yield from self.get_battery()
        _LOGGER.debug("Got battery data for Leaf")

        if batteryResponse.answer == 200:
            self.data[DATA_BATTERY] = round(batteryResponse.battery_percent, 0)
            #self.data[DATA_BATTERY] = 1
            self.data[DATA_CHARGING] = batteryResponse.is_charging

        _LOGGER.debug("Battery Response: ")
        _LOGGER.debug(batteryResponse.__dict__)

        climateResponse = self.get_climate()
        _LOGGER.debug("Got climate data for Leaf")
        self.data[DATA_CLIMATE] = climateResponse

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

    @asyncio.coroutine
    def get_battery(self):
        request = self.leaf.request_update()
        battery_status = self.leaf.get_status_from_update(request)
        while battery_status is None:
            _LOGGER.debug("Battery data not in yet.")
            yield from asyncio.sleep(5)
            battery_status = self.leaf.get_status_from_update(request)

        return battery_status

    def get_climate(self):
        request = self.leaf.get_latest_hvac_status()
        if request is None:
            return False
        else:
            return request.is_hvac_running

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
            yield from asyncio.sleep(5)
            location_status = self.leaf.get_status_from_location(request)

        return location_status

    def start_charging(self):
        return self.leaf.start_charging()


class LeafEntity(Entity):
    def __init__(self, controller, data):
        self.controller = controller
        self.data = data

    def added_to_hass(self):
        """Register callbacks."""
        self.log_registration()
        async_dispatcher_connect(
            self.data.hass, SIGNAL_UPDATE_LEAF, self._update_callback)

    def _update_callback(self):
        """Callback update method."""
        _LOGGER.debug("Got dispatcher update from Leaf platform")
        self.schedule_update_ha_state(True)
