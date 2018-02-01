"""
Support for the Nissan Leaf Carwings/Nissan Connect API.

Please note this is the pre-2018 API, which is still functional in the US.
The old API should continue to work as the new one is not being released outside the US.

Documentation pages have not been created yet, here is an example configuration block:

nissan_leaf:
  username: "username"
  password: "password"
  nissan_connect: false
  region: 'NE'
  update_interval: 30
  update_interval_charging: 15
  update_interval_climate: 5
  force_miles: true
"""

import voluptuous as vol
import logging
from datetime import timedelta, datetime
import time
import urllib

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.entity import Entity
import asyncio
import sys
from homeassistant.helpers.event import track_time_interval

# Currently waiting on the pycarwings2 author to pull this PR in and update pip, so using my fork for now.
# https://github.com/jdhorne/pycarwings2/pull/28

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
CONF_CHARGING_INTERVAL = 'update_interval_charging'
CONF_CLIMATE_INTERVAL = 'update_interval_climate'
CONF_REGION = 'region'
CONF_VALID_REGIONS = ['NNA', 'NE', 'NCI', 'NMA', 'NML']
CONF_FORCE_MILES = 'force_miles'
DEFAULT_INTERVAL = 30
DEFAULT_CHARGING_INTERVAL = 15
DEFAULT_CLIMATE_INTERVAL = 5

CHECK_INTERVAL = 10

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_REGION): vol.In(CONF_VALID_REGIONS),
        vol.Optional(CONF_NCONNECT, default=True): cv.boolean,
        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): cv.positive_int,
        vol.Optional(CONF_CHARGING_INTERVAL, default=DEFAULT_CHARGING_INTERVAL): cv.positive_int,
        vol.Optional(CONF_CLIMATE_INTERVAL, default=DEFAULT_CLIMATE_INTERVAL): cv.positive_int,
        vol.Optional(CONF_FORCE_MILES, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

LEAF_COMPONENTS = [
    'sensor', 'switch', 'binary_sensor'
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
        if (component != 'device_tracker') or (config[DOMAIN][CONF_NCONNECT] is True):
            load_platform(hass, component, DOMAIN, {}, config)

    # hass.data[DATA_LEAF][leaf.vin].refresh_leaf_if_necessary(0)

    return True


class LeafDataStore:

    def __init__(self, leaf, hass, config):
        self.leaf = leaf
        self.config = config
        #self.nissan_connect = config[DOMAIN][CONF_NCONNECT]
        self.nissan_connect = False  # Disabled until tested and implemented
        self.hass = hass
        self.data = {}
        self.data[DATA_CLIMATE] = False
        self.data[DATA_BATTERY] = 0
        self.data[DATA_CHARGING] = False
        self.data[DATA_LOCATION] = False
        self.data[DATA_RANGE_AC] = 0
        self.data[DATA_RANGE_AC_OFF] = 0
        self.data[DATA_PLUGGED_IN] = False
        self.lastCheck = None
        track_time_interval(
            hass, self.refresh_leaf_if_necessary, timedelta(seconds=CHECK_INTERVAL))

    def refresh_leaf_if_necessary(self, event_time):
        result = False
        now = datetime.today()

        if self.lastCheck is None:
            _LOGGER.debug("Firing Refresh on " + self.leaf.vin +
                          " as there has not been one yet.")
            result = True
        elif self.lastCheck + timedelta(minutes=self.config[DOMAIN][CONF_INTERVAL]) < now:
            _LOGGER.debug("Firing Refresh on " + self.leaf.vin +
                          " as the interval has passed.")
            result = True
        elif self.data[DATA_CHARGING] is True and self.lastCheck + timedelta(minutes=self.config[DOMAIN][CONF_CHARGING_INTERVAL]) < now:
            _LOGGER.debug("Firing Refresh on " + self.leaf.vin +
                          " as it's charging and the charging interval has passed.")
            result = True
        elif self.data[DATA_CLIMATE] is True and self.lastCheck + timedelta(minutes=self.config[DOMAIN][CONF_CLIMATE_INTERVAL]) < now:
            _LOGGER.debug("Firing Refresh on " + self.leaf.vin +
                          " as climate control is on and the interval has passed.")
            result = True

        if result is True:
            self.refresh_data()

    def refresh_data(self):
        _LOGGER.debug("Updating Nissan Leaf Data")

        self.lastCheck = datetime.today()

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

        self.signal_components()

    def signal_components(self):
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

            _LOGGER.debug(climate_result.__dict__)

            self.signal_components()

            return climate_result.is_hvac_running
        else:
            request = self.leaf.stop_climate_control()
            climate_result = self.leaf.get_stop_climate_control_result(request)

            while climate_result is None:
                _LOGGER.debug("Climate data not in yet.")
                time.sleep(5)
                climate_result = self.leaf.get_stop_climate_control_result(
                    request)

            _LOGGER.debug(climate_result.__dict__)

            self.signal_components()

            return climate_result.is_hvac_running is False

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

    @property
    def device_state_attributes(self):
        return {
            'homebridge_serial': self.car.leaf.vin,
            'homebridge_mfg': 'Nissan',
            'homebridge_model': 'Leaf'
        }

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
