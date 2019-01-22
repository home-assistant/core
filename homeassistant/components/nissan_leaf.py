"""
Support for the Nissan Leaf Carwings/Nissan Connect API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nissan_leaf
"""

import logging
from datetime import timedelta, datetime
import urllib
import asyncio
import sys
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['pycarwings2==2.6']

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

INITIAL_UPDATE = timedelta(seconds=15)
MIN_UPDATE_INTERVAL = timedelta(minutes=2)
DEFAULT_INTERVAL = timedelta(hours=1)
DEFAULT_CHARGING_INTERVAL = timedelta(minutes=15)
DEFAULT_CLIMATE_INTERVAL = timedelta(minutes=5)
RESTRICTED_BATTERY = 2
RESTRICTED_INTERVAL = timedelta(hours=12)

MAX_RESPONSE_ATTEMPTS = 22

PYCARWINGS2_SLEEP = 30

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_REGION): vol.In(CONF_VALID_REGIONS),
        vol.Optional(CONF_NCONNECT, default=True): cv.boolean,
        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): (
            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))),
        vol.Optional(CONF_CHARGING_INTERVAL,
                     default=DEFAULT_CHARGING_INTERVAL): (
                         vol.All(cv.time_period,
                                 vol.Clamp(
                                     min=MIN_UPDATE_INTERVAL))),
        vol.Optional(CONF_CLIMATE_INTERVAL,
                     default=DEFAULT_CLIMATE_INTERVAL): (
                         vol.All(cv.time_period,
                                 vol.Clamp(
                                     min=MIN_UPDATE_INTERVAL))),
        vol.Optional(CONF_FORCE_MILES, default=False): cv.boolean
    })])
}, extra=vol.ALLOW_EXTRA)

LEAF_COMPONENTS = [
    'sensor', 'switch', 'binary_sensor', 'device_tracker'
]

SIGNAL_UPDATE_LEAF = 'nissan_leaf_update'


@asyncio.coroutine
def async_setup(hass, config):
    """Set-up the Nissan Leaf component."""
    import pycarwings2

    async def async_setup_leaf(car_config):
        """Set-up a car."""
        _LOGGER.debug("Logging into You+Nissan...")

        username = car_config[CONF_USERNAME]
        password = car_config[CONF_PASSWORD]
        region = car_config[CONF_REGION]
        leaf = None

        async def leaf_login():
            nonlocal leaf
            sess = pycarwings2.Session(username, password, region)
            leaf = sess.get_leaf()

        try:
            # this might need to be made async (somehow) causes
            # homeassistant to be slow to start
            await hass.async_add_job(leaf_login)
        except(RuntimeError, urllib.error.HTTPError):
            _LOGGER.error(
                "Unable to connect to Nissan Connect with "
                "username and password")
            return False
        except KeyError:
            _LOGGER.error(
                "Unable to fetch car details..."
                " do you actually have a Leaf connected to your account?")
            return False
        except pycarwings2.CarwingsError:
            _LOGGER.error(
                "An unknown error occurred while connecting to Nissan: %s",
                sys.exc_info()[0])
            return False

        _LOGGER.info("Successfully logged in and fetched Leaf info")
        _LOGGER.info(
            "WARNING: This may poll your Leaf too often, and drain the 12V"
            " battery.  If you drain your cars 12V battery it WILL NOT START"
            " as the drive train battery won't connect."
            " Don't set the intervals too low.")

        data_store = LeafDataStore(leaf, hass, car_config)
        hass.data[DATA_LEAF][leaf.vin] = data_store

        for component in LEAF_COMPONENTS:
            if (component != 'device_tracker' or
                    car_config[CONF_NCONNECT] is True):
                load_platform(hass, component, DOMAIN, {}, car_config)

        async_track_point_in_utc_time(hass, data_store.async_update_data,
                                      utcnow() + INITIAL_UPDATE)

    hass.data[DATA_LEAF] = {}
    tasks = [async_setup_leaf(car) for car in config[DOMAIN]]
    if tasks:
        yield from asyncio.wait(tasks, loop=hass.loop)

    return True


class LeafDataStore:
    """Nissan Leaf Data Store."""

    def __init__(self, leaf, hass, car_config):
        """Initialise the data store."""
        self.leaf = leaf
        self.car_config = car_config
        self.nissan_connect = car_config[CONF_NCONNECT]
        self.force_miles = car_config[CONF_FORCE_MILES]
        self.hass = hass
        self.data = {}
        self.data[DATA_CLIMATE] = False
        self.data[DATA_BATTERY] = 0
        self.data[DATA_CHARGING] = False
        self.data[DATA_LOCATION] = False
        self.data[DATA_RANGE_AC] = 0
        self.data[DATA_RANGE_AC_OFF] = 0
        self.data[DATA_PLUGGED_IN] = False
        self.last_check = None
        self.last_battery_response = None
        self.request_in_progress = False

    @asyncio.coroutine
    async def async_update_data(self, now):
        """Update data from nissan leaf."""
        await self.async_refresh_data(now)
        next_interval = self.get_next_interval()
        _LOGGER.debug("Next interval=%s", next_interval)
        async_track_point_in_utc_time(
            self.hass, self.async_update_data, next_interval)

    def get_next_interval(self):
        """Calculate when the next update should occur."""
        base_interval = self.car_config[CONF_INTERVAL]
        climate_interval = self.car_config[CONF_CLIMATE_INTERVAL]
        charging_interval = self.car_config[CONF_CHARGING_INTERVAL]

        # The 12V battery is used when communicating with Nissan servers.
        # The 12V battery is charged from the traction battery when not
        # connected and when the traction battery has enough charge. To
        # avoid draining the 12V battery we shall restrict the update
        # frequency if low battery detected.
        if (self.last_battery_response is not None and
                self.data[DATA_CHARGING] is False and
                self.data[DATA_BATTERY] <= RESTRICTED_BATTERY):
            _LOGGER.info("Low battery so restricting refresh frequency (%s)",
                         self.leaf.nickname)
            interval = RESTRICTED_INTERVAL
        else:
            intervals = [base_interval]
            _LOGGER.debug("Could use base interval=%s", base_interval)

            if self.data[DATA_CHARGING]:
                intervals.append(charging_interval)
                _LOGGER.debug("Could use charging interval=%s",
                              charging_interval)

            if self.data[DATA_CLIMATE]:
                intervals.append(climate_interval)
                _LOGGER.debug("Could use climate interval=%s",
                              climate_interval)

            interval = min(intervals)
            _LOGGER.debug("Resulting interval=%s", interval)

        return utcnow() + interval

    async def async_refresh_data(self, now):
        """Refresh the leaf data and update the datastore."""
        from pycarwings2 import CarwingsError

        if self.request_in_progress:
            _LOGGER.debug("Refresh currently in progress for %s",
                          self.leaf.nickname)
            return

        _LOGGER.debug("Updating Nissan Leaf Data")

        self.last_check = datetime.today()
        self.request_in_progress = True

        server_response = await self.async_get_battery()

        if server_response is not None:
            _LOGGER.debug("Server Response: %s", server_response.__dict__)

            if server_response.answer['status'] == 200:
                self.data[DATA_BATTERY] = server_response.battery_percent
                self.data[DATA_RANGE_AC] = (
                    server_response.cruising_range_ac_on_km
                )
                self.data[DATA_RANGE_AC_OFF] = (
                    server_response.cruising_range_ac_off_km
                )
                self.data[DATA_PLUGGED_IN] = (
                    server_response.is_connected
                )
                async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)
                self.last_battery_response = utcnow()

        # Climate response only updated if battery data updated first.
        if server_response is not None:
            try:
                climate_response = await self.async_get_climate()
                if climate_response is not None:
                    _LOGGER.debug("Got climate data for Leaf: %s",
                                  climate_response.__dict__)
                    self.data[DATA_CLIMATE] = climate_response.is_hvac_running
            except CarwingsError:
                _LOGGER.error("Error fetching climate info")

        if self.nissan_connect:
            try:
                location_response = await self.async_get_location()

                if location_response is None:
                    _LOGGER.debug("Empty Location Response Received")
                    self.data[DATA_LOCATION] = None
                else:
                    _LOGGER.debug("Got location data for Leaf")
                    self.data[DATA_LOCATION] = location_response

                    _LOGGER.debug("Location Response: %s",
                                  location_response.__dict__)
            except CarwingsError:
                _LOGGER.error("Error fetching location info")

        self.request_in_progress = False
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)

    @staticmethod
    def _extract_start_date(battery_info):
        """Extract the server date from the battery response."""
        try:
            return battery_info.answer[
                "BatteryStatusRecords"]["OperationDateAndTime"]
        except KeyError:
            return None

    async def async_get_battery(self):
        """Request battery update from Nissan servers."""
        from pycarwings2 import CarwingsError
        try:
            # First, check nissan servers for the latest data
            start_server_info = await self.hass.async_add_job(
                self.leaf.get_latest_battery_status
            )

            # Store the date from the nissan servers
            start_date = self._extract_start_date(start_server_info)
            if start_date is None:
                _LOGGER.info("No start date from servers. Aborting")
                return None

            _LOGGER.info("Start server date=%s", start_date)

            # Request battery update from the car
            _LOGGER.info("Requesting battery update, %s", self.leaf.vin)
            request = await self.hass.async_add_job(self.leaf.request_update)
            if not request:
                _LOGGER.error("Battery update request failed")
                return None

            for _ in range(MAX_RESPONSE_ATTEMPTS):
                _LOGGER.info("Waiting %s seconds for battery update",
                             PYCARWINGS2_SLEEP)
                await asyncio.sleep(PYCARWINGS2_SLEEP)

                # Note leaf.get_status_from_update is always returning 0, so
                # don't try to use it anymore.
                server_info = await self.hass.async_add_job(
                    self.leaf.get_latest_battery_status
                )

                latest_date = self._extract_start_date(server_info)
                _LOGGER.info("Latest server date=%s", latest_date)
                if latest_date is not None and latest_date != start_date:
                    return server_info

            _LOGGER.info("%s attempts exceeded return latest data from server",
                         MAX_RESPONSE_ATTEMPTS)
            return server_info
        except CarwingsError:
            _LOGGER.error("An error occurred getting battery status.")
            return None

    async def async_get_climate(self):
        """Request climate data from Nissan servers."""
        from pycarwings2 import CarwingsError
        try:
            request = await self.hass.async_add_job(
                self.leaf.get_latest_hvac_status
            )
            return request
        except CarwingsError:
            _LOGGER.error(
                "An error occurred communicating with the car %s",
                self.leaf.vin)
            return None

    async def async_set_climate(self, toggle):
        """Set climate control mode via Nissan servers."""
        climate_result = None
        if toggle:
            _LOGGER.info("Requesting climate turn on for %s", self.leaf.vin)
            request = await self.hass.async_add_job(
                self.leaf.start_climate_control
            )
            for attempt in range(MAX_RESPONSE_ATTEMPTS):
                if attempt > 0:
                    _LOGGER.info("Climate data not in yet (%s) (%s). "
                                 "Waiting (%s) seconds.", self.leaf.vin,
                                 attempt, PYCARWINGS2_SLEEP)
                    await asyncio.sleep(PYCARWINGS2_SLEEP)

                climate_result = await self.hass.async_add_job(
                    self.leaf.get_start_climate_control_result, request
                )

                if climate_result is not None:
                    break

        else:
            _LOGGER.info("Requesting climate turn off for %s", self.leaf.vin)
            request = await self.hass.async_add_job(
                self.leaf.stop_climate_control
            )

            for attempt in range(MAX_RESPONSE_ATTEMPTS):
                if attempt > 0:
                    _LOGGER.debug("Climate data not in yet. (%s) (%s). "
                                  "Waiting 5 seconds", self.leaf.vin, attempt)
                    await asyncio.sleep(5)

                climate_result = await self.hass.async_add_job(
                    self.leaf.get_stop_climate_control_result, request
                )

                if climate_result is not None:
                    break

        if climate_result is not None:
            _LOGGER.debug("Climate result: %s", climate_result.__dict__)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)
            return climate_result.is_hvac_running == toggle

        _LOGGER.debug("Climate result not returned by Nissan servers")
        return False

    async def async_get_location(self):
        """Get location from Nissan servers."""
        request = await self.hass.async_add_job(self.leaf.request_location)
        for attempt in range(MAX_RESPONSE_ATTEMPTS):
            if attempt > 0:
                _LOGGER.debug("Location data not in yet. (%s) (%s). "
                              "Waiting 5 seconds", self.leaf.vin, attempt)
                await asyncio.sleep(5)

            location_status = await self.hass.async_add_job(
                self.leaf.get_status_from_location, request
            )

            if location_status is not None:
                _LOGGER.debug("Location_status=%s", location_status.__dict__)
                break

        async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)
        return location_status

    async def async_start_charging(self):
        """Request start charging via Nissan servers."""
        # Send the command to request charging is started to Nissan servers.
        # If that completes OK then trigger a fresh update to pull the
        # charging status from the car after waiting a minute for the
        # charging request to reach the car.
        result = await self.hass.async_add_job(self.leaf.start_charging)
        if result:
            _LOGGER.debug("Start charging sent, "
                          "request updated data in 1 minute")
            check_charge_at = utcnow() + timedelta(minutes=1)
            async_track_point_in_utc_time(
                self.hass, self.async_refresh_data, check_charge_at)


class LeafEntity(Entity):
    """Base class for Nissan Leaf entity."""

    def __init__(self, car):
        """Store LeafDataStore upon init."""
        self.car = car

    def log_registration(self):
        """Log registration."""
        _LOGGER.debug(
            "Registered %s component for VIN %s",
            self.__class__.__name__, self.car.leaf.vin)

    @property
    def device_state_attributes(self):
        """Return default attributes for Nissan Leaf entities."""
        return {
            'homebridge_serial': self.car.leaf.vin,
            'homebridge_mfg': 'Nissan',
            'homebridge_model': 'Leaf'
        }

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.log_registration()
        async_dispatcher_connect(
            self.car.hass, SIGNAL_UPDATE_LEAF, self._update_callback)

    def _update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state(True)
