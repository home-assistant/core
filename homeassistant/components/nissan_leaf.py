"""
Support for the Nissan Leaf Carwings/Nissan Connect API.

Please note this is the pre-2018 API, which is still functional in the US.
The old API should continue to work for the forseeable future.

Documentation has not been created yet, here is an example configuration block:

nissan_leaf:
  - username: "username"
    password: "password"
    nissan_connect: true
    region: 'NE'
    update_interval:
      hours: 1
    update_interval_charging:
      minutes: 15
    update_interval_climate:
      minutes: 5
    force_miles: true


Notes for the above:

region: Must be one of
           'NE' (Europe),
           'NNA' (US),
           'NCI' (Canada),
           'NMA' (Australia),
           'NML' (Japan)
nissan_connect: If your car has the updated head unit (Nissan Connect rather
                than Car Wings) then you can pull the location, shown in a
                device tracker. If you have a pre-2016 24kWh Leaf then you
                will have CarWings and should set this to false, or it will
                crash the component.
update_interval: The interval between updates if AC is off and not charging
update_interval_charging: The interval between updates if charging
update_interval_climate: The interval between updates if climate control is on

Notes for testers:

Please report bugs using the following logger config.

logger:
  default: critical
  logs:
    homeassistant.components.nissan_leaf: debug
    homeassistant.components.sensor.nissan_leaf: debug
    homeassistant.components.switch.nissan_leaf: debug
    homeassistant.components.device_tracker.nissan_leaf: debug


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

# If testing then use the following kinds of URLs
#
# REQUIREMENTS = ['https://github.com/filcole/pycarwings2/archive/master.zip'
#                 '#pycarwings2']
# REQUIREMENTS = ['https://test-files.pythonhosted.org/packages/7c/ad/
#      ee27988357f1710ca9ced1a60263486415f054003ca6fa396922ca6b6bbf/
#      pycarwings2-2.2.tar.gz'
#                 '#pycarwings2']
# REQUIREMENTS = ['file:///home/phil/repos/pycarwings2ve/pycarwings2/
#      dist/pycarwings2-2.2.tar.gz'
#                 '#pycarwings2']
REQUIREMENTS = ['pycarwings2==2.2']

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

MIN_UPDATE_INTERVAL = timedelta(minutes=2)
DEFAULT_INTERVAL = timedelta(minutes=30)
DEFAULT_CHARGING_INTERVAL = timedelta(minutes=15)
DEFAULT_CLIMATE_INTERVAL = timedelta(minutes=5)
RESTRICTED_BATTERY = 2
RESTRICTED_INTERVAL = timedelta(hours=12)

MAX_RESPONSE_ATTEMPTS = 22

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
    """Setup the nissan leaf component."""
    import pycarwings2

    async def async_setup_leaf(car_config):
        """Setup a leaf car."""
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
        await hass.async_add_job(data_store.async_update_data, None)

        for component in LEAF_COMPONENTS:
            if (component != 'device_tracker' or
                    car_config[CONF_NCONNECT] is True):
                load_platform(hass, component, DOMAIN, {}, car_config)

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
        # connected # and when the traction battery has enough charge. To
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

        (battery_response, server_response) = await self.async_get_battery()

        if battery_response is not None:
            _LOGGER.debug("Battery Response: ")
            _LOGGER.debug(battery_response.__dict__)

            if battery_response.answer['status'] == 200:
                if int(battery_response.battery_capacity) > 100:
                    self.data[DATA_BATTERY] = (
                        battery_response.battery_percent * 0.05
                    )
                else:
                    self.data[DATA_BATTERY] = battery_response.battery_percent

                self.data[DATA_CHARGING] = battery_response.is_charging
                self.data[DATA_PLUGGED_IN] = battery_response.is_connected
                self.data[DATA_RANGE_AC] = (
                    battery_response.cruising_range_ac_on_km
                )
                self.data[DATA_RANGE_AC_OFF] = (
                    battery_response.cruising_range_ac_off_km
                )
                self.signal_components()
                self.last_battery_response = utcnow()

        if server_response is not None:
            _LOGGER.debug("Server Response: ")
            _LOGGER.debug(server_response.__dict__)

            if server_response.answer['status'] == 200:
                if server_response.state_of_charge is not None:
                    self.data[DATA_BATTERY] = int(
                        server_response.state_of_charge
                    )
                else:
                    self.data[DATA_BATTERY] = server_response.battery_percent

                self.data[DATA_RANGE_AC] = (
                    server_response.cruising_range_ac_on_km
                )
                self.data[DATA_RANGE_AC_OFF] = (
                    server_response.cruising_range_ac_off_km
                )
                self.signal_components()
                self.last_battery_response = utcnow()

        # Climate response only updated if battery data updated first.
        if (battery_response is not None) or (server_response is not None):

            climate_response = await self.async_get_climate()
            if climate_response is not None:
                _LOGGER.debug("Got climate data for Leaf.")
                _LOGGER.debug(climate_response.__dict__)
                self.data[DATA_CLIMATE] = climate_response.is_hvac_running

        if self.nissan_connect:
            try:
                location_response = await self.async_get_location()

                if location_response is None:
                    _LOGGER.debug("Empty Location Response Received")
                    self.data[DATA_LOCATION] = None
                else:
                    _LOGGER.debug("Got location data for Leaf")
                    self.data[DATA_LOCATION] = location_response

                    _LOGGER.debug("Location Response: ")
                    _LOGGER.debug(location_response.__dict__)
            except CarwingsError:
                _LOGGER.error("Error fetching location info")

        self.request_in_progress = False
        self.signal_components()

    def signal_components(self):
        """Signal components to refresh."""
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)

    async def async_get_battery(self):
        """Request battery update from Nissan servers."""
        # First, check nissan servers for the latest data
        start_server_info = await self.hass.async_add_job(
            self.leaf.get_latest_battery_status
        )

        # Store the date from the nissan servers
        start_date = start_server_info.answer[
            "BatteryStatusRecords"]["OperationDateAndTime"]
        _LOGGER.info("Start server date=%s", start_date)

        # Request battery update from the car
        _LOGGER.info("Requesting battery update, %s", self.leaf.vin)
        request = await self.hass.async_add_job(self.leaf.request_update)

        for attempt in range(MAX_RESPONSE_ATTEMPTS):
            await asyncio.sleep(5)
            battery_status = await self.hass.async_add_job(
                self.leaf.get_status_from_update, request
            )
            if battery_status is not None:
                return (battery_status, None)

            _LOGGER.info("Battery data (%s) not in yet (%s). "
                         "Seeing if nissan server data has changed",
                         self.leaf.vin, attempt)
            server_info = await self.hass.async_add_job(
                self.leaf.get_latest_battery_status
            )
            latest_date = server_info.answer[
                "BatteryStatusRecords"]["OperationDateAndTime"]
            _LOGGER.info("Latest server date=%s", latest_date)
            if latest_date != start_date:
                _LOGGER.info("Using updated server info instead "
                             "of waiting for request_updated")
                return (None, server_info)

        _LOGGER.info("%s attempts exceeded return latest data from server",
                     MAX_RESPONSE_ATTEMPTS)
        return (None, server_info)

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
                                 "Waiting 5 seconds.", self.leaf.vin, attempt)
                    await asyncio.sleep(5)

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
            _LOGGER.debug("Climate result:")
            _LOGGER.debug(climate_result.__dict__)
            self.signal_components()
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
                _LOGGER.debug(location_status.__dict__)
                break

        self.signal_components()
        return location_status

    async def async_start_charging(self):
        """Request start charging via Nissan servers."""
        # Send the command to request charging is started to Nissan servers.
        # If that completes OK then trigger a fresh update to pull the
        # charging status from the car after waiting a minute for the
        # charging request to reach the car.
        result = await self.hass.async_add_job(self.leaf.start_charging)
        if result:
            _LOGGER.debug("Start charging sent, request updated data in 1 minute")
            check_charge_at = utcnow() + timedelta(minutes=1)
            async_track_point_in_utc_time(
                self.hass, self.async_refresh_data, check_charge_at)


class LeafEntity(Entity):
    """Base class for Nissan Leaf entity."""

    def __init__(self, car):
        """Store LeafDataStore upon init."""
        self.car = car

    def log_registration(self):
        """Abstract log registration."""
        raise NotImplementedError("Please implement this method")

    @property
    def device_state_attributes(self):
        """Default attributes for Nissan Leaf entities."""
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
        """Callback update method."""
        self.schedule_update_ha_state(True)
