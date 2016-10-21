"""
Platform that supports scanning iCloud.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/icloud/
"""
import logging
from datetime import datetime, timedelta
from math import floor
import random

import voluptuous as vol

from pytz import timezone
import pytz

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import (Entity, generate_entity_id)
from homeassistant.components.device_tracker import see
from homeassistant.helpers.event import (track_state_change,
                                         track_utc_time_change)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import template
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util
from homeassistant.util.location import distance

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.9.1']

DEPENDENCIES = ['zone', 'device_tracker']

CONF_IGNORED_DEVICES = 'ignored_devices'
CONF_GMTT = 'google_maps_travel_time'
CONF_COOKIEDIRECTORY = 'cookiedirectory'

# entity attributes
ATTR_ACCOUNTNAME = 'account_name'
ATTR_INTERVAL = 'interval'
ATTR_DEVICENAME = 'device_name'
ATTR_BATTERY = 'battery'
ATTR_DISTANCE = 'distance'
ATTR_DEVICESTATUS = 'device_status'
ATTR_LOWPOWERMODE = 'low_power_mode'
ATTR_BATTERYSTATUS = 'battery_status'
ATTR_GMTT = 'google_maps_travel_time'
ATTR_GMTT_DURATION = 'gmtt_duration'
ATTR_GMTT_ORIGIN = 'gmtt_origin'

ICLOUDTRACKERS = {}

DOMAIN = 'icloud'
DOMAIN2 = 'idevice'

ENTITY_ID_FORMAT_ICLOUD = DOMAIN + '.{}'
ENTITY_ID_FORMAT_DEVICE = DOMAIN2 + '.{}'

DEVICESTATUSSET = ['features', 'maxMsgChar', 'darkWake', 'fmlyShare',
                   'deviceStatus', 'remoteLock', 'activationLocked',
                   'deviceClass', 'id', 'deviceModel', 'rawDeviceModel',
                   'passcodeLength', 'canWipeAfterLock', 'trackingInfo',
                   'location', 'msg', 'batteryLevel', 'remoteWipe',
                   'thisDevice', 'snd', 'prsId', 'wipeInProgress',
                   'lowPowerMode', 'lostModeEnabled', 'isLocating',
                   'lostModeCapable', 'mesg', 'name', 'batteryStatus',
                   'lockedTimestamp', 'lostTimestamp', 'locationCapable',
                   'deviceDisplayName', 'lostDevice', 'deviceColor',
                   'wipedTimestamp', 'modelDisplayName', 'locationEnabled',
                   'isMac', 'locFoundEnabled']

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ACCOUNTNAME): cv.string,
    vol.Optional(ATTR_DEVICENAME): cv.string,
    vol.Optional(ATTR_INTERVAL): cv.positive_int,
})

ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_COOKIEDIRECTORY, default=None): cv.string,
    vol.Optional(CONF_IGNORED_DEVICES, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_GMTT, default={}):
        vol.Schema({cv.string: cv.string}),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(cv.slug): ACCOUNT_SCHEMA,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):  # pylint: disable=too-many-locals,too-many-branches
    """Set up the iCloud Scanner."""
    for account, account_config in config[DOMAIN].items():
        # Get the username and password from the configuration
        username = account_config.get(CONF_USERNAME)
        password = account_config.get(CONF_PASSWORD)
        cookiedirectory = account_config.get(CONF_COOKIEDIRECTORY)

        ignored_devices = []
        ignored_dev = account_config.get(CONF_IGNORED_DEVICES)
        for each_dev in ignored_dev:
            ignored_devices.append(each_dev)

        googletraveltime = {}
        gttconfig = account_config.get(CONF_GMTT)
        for google, googleconfig in gttconfig.items():
            googletraveltime[google] = googleconfig

        icloudaccount = Icloud(hass, username, password, cookiedirectory,
                               account, ignored_devices, googletraveltime)
        icloudaccount.update_ha_state()
        ICLOUDTRACKERS[account] = icloudaccount
        if ICLOUDTRACKERS[account].api is not None:
            for device in ICLOUDTRACKERS[account].devices:
                iclouddevice = ICLOUDTRACKERS[account].devices[device]
                devicename = iclouddevice.devicename.lower()
                track_state_change(hass,
                                   'device_tracker.' + devicename,
                                   iclouddevice.devicechanged)

    if not ICLOUDTRACKERS:
        _LOGGER.error("No ICLOUDTRACKERS added")
        return False

    randomseconds = random.randint(10, 59)

    def lost_iphone(call):
        """Call the lost iphone function if the device is found."""
        accountname = call.data.get(ATTR_ACCOUNTNAME)
        devicename = call.data.get(ATTR_DEVICENAME)
        if accountname is None:
            for account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].lost_iphone(devicename)
        elif accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].lost_iphone(devicename)

    hass.services.register(DOMAIN, 'lost_iphone',
                           lost_iphone)

    def update_icloud(call):
        """Call the update function of an icloud account."""
        accountname = call.data.get(ATTR_ACCOUNTNAME)
        devicename = call.data.get(ATTR_DEVICENAME)
        if accountname is None:
            for account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].update_icloud(devicename)
        elif accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].update_icloud(devicename)
    hass.services.register(DOMAIN,
                           'update_icloud', update_icloud)

    def keep_alive(now):
        """Keep the api logged in of all account."""
        for accountname in ICLOUDTRACKERS:
            try:
                ICLOUDTRACKERS[accountname].keep_alive()
            except ValueError:
                _LOGGER.error("something went wrong for account %s, " +
                              "retrying in a minute", accountname)

    track_utc_time_change(
        hass, keep_alive,
        second=randomseconds
    )

    def setinterval(call):
        """Call the update function of an icloud account."""
        accountname = call.data.get(ATTR_ACCOUNTNAME)
        interval = call.data.get(ATTR_INTERVAL)
        devicename = call.data.get(ATTR_DEVICENAME)
        if accountname is None:
            for account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].setinterval(interval, devicename)
        elif accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].setinterval(interval, devicename)

    hass.services.register(DOMAIN,
                           'setinterval', setinterval)

    # Tells the bootstrapper that the component was successfully initialized
    return True


class IDevice(Entity):  # pylint: disable=too-many-instance-attributes
    """Represent an iDevice in Home Assistant."""

    def __init__(self, hass, icloudobject, name, identifier, googletraveltime):
        """Initialize the iDevice."""
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.icloudobject = icloudobject
        self.identifier = identifier
        self._request_interval_seconds = 60
        self._interval = 1
        self.api = icloudobject.api
        self._overridestate = None
        self._devicestatuscode = None

        self._attrs = {}
        self._attrs[ATTR_DEVICENAME] = name
        if googletraveltime is not None:
            self._attrs[ATTR_GMTT] = googletraveltime

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT_DEVICE, self._attrs[ATTR_DEVICENAME],
            hass=self.hass)

    @property
    def state(self):
        """Return the state of the iDevice."""
        return self._interval

    @property
    def unit_of_measurement(self):
        """Unit of measurement of this entity."""
        return "minutes"

    @property
    def state_attributes(self):
        """Return the attributes of the iDevice."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return 'mdi:cellphone-iphone'

    @property
    def devicename(self):
        """Return the devicename of the device."""
        return self._attrs[ATTR_DEVICENAME]

    def keep_alive(self):
        """Keep the api alive."""
        currentminutes = dt_util.now().hour * 60 + dt_util.now().minute
        if currentminutes % self._interval == 0:
            self.update_icloud()
        elif self._interval > 10 and currentminutes % self._interval in [2, 4]:
            self.update_icloud()

        if ATTR_GMTT in self._attrs:
            gttstate = self.hass.states.get(self._attrs[ATTR_GMTT])
            if gttstate is not None:
                if 'origin_addresses' in gttstate.attributes:
                    duration = gttstate.state
                    origin = gttstate.attributes['origin_addresses']
                    self._attrs[ATTR_GMTT_DURATION] = duration
                    self._attrs[ATTR_GMTT_ORIGIN] = origin
                    self.update_ha_state()

    def lost_iphone(self):
        """Call the lost iphone function if the device is found."""
        if self.api is not None:
            self.api.authenticate()
            self.identifier.play_sound()

    @staticmethod
    def data_is_accurate(data):
        """Check if location data is accurate."""
        if not data:
            return False
        elif not data['locationFinished']:
            return False
        return True

    def update_icloud(self):
        """Authenticate against iCloud and scan for devices."""
        if self.api is not None:
            from pyicloud.exceptions import PyiCloudNoDevicesException

            try:
                status = self.identifier.status(DEVICESTATUSSET)
                dev_id = slugify(status['name'].replace(' ', '', 99))
                self._devicestatuscode = status['deviceStatus']
                if self._devicestatuscode == '200':
                    self._attrs[ATTR_DEVICESTATUS] = 'online'
                elif self._devicestatuscode == '201':
                    self._attrs[ATTR_DEVICESTATUS] = 'offline'
                elif self._devicestatuscode == '203':
                    self._attrs[ATTR_DEVICESTATUS] = 'pending'
                elif self._devicestatuscode == '204':
                    self._attrs[ATTR_DEVICESTATUS] = 'unregistered'
                else:
                    self._attrs[ATTR_DEVICESTATUS] = 'error'
                self._attrs[ATTR_LOWPOWERMODE] = status['lowPowerMode']
                self._attrs[ATTR_BATTERYSTATUS] = status['batteryStatus']
                self.update_ha_state()
                status = self.identifier.status(DEVICESTATUSSET)
                battery = status['batteryLevel']*100
                location = status['location']
                if location:
                    see(hass=self.hass, dev_id=dev_id,
                        host_name=status['name'], gps=(location['latitude'],
                                                       location['longitude']),
                        battery=battery,
                        gps_accuracy=location['horizontalAccuracy'])
            except PyiCloudNoDevicesException:
                _LOGGER.error('No iCloud Devices found!')

    def get_default_interval(self):
        """Get default interval of iDevice."""
        devid = 'device_tracker.' + self._attrs[ATTR_DEVICENAME]
        devicestate = self.hass.states.get(devid)
        self._overridestate = None
        self.devicechanged(self._attrs[ATTR_DEVICENAME], None, devicestate)

    def setinterval(self, interval=None):
        """Set interval of iDevice."""
        if interval is not None:
            devid = 'device_tracker.' + self._attrs[ATTR_DEVICENAME]
            devicestate = self.hass.states.get(devid)
            if devicestate is not None:
                self._overridestate = devicestate.state
            self._interval = interval
        else:
            self.get_default_interval()
        self.update_ha_state()
        self.update_icloud()

    def devicechanged(self, entity, old_state, new_state):
        """Calculate new interval."""
        # pylint: disable=too-many-branches
        if entity is None:
            return

        self._attrs[ATTR_DISTANCE] = None
        if 'latitude' in new_state.attributes:
            device_state_lat = new_state.attributes['latitude']
            device_state_long = new_state.attributes['longitude']
            zone_state = self.hass.states.get('zone.home')
            zone_state_lat = zone_state.attributes['latitude']
            zone_state_long = zone_state.attributes['longitude']
            self._attrs[ATTR_DISTANCE] = distance(
                device_state_lat, device_state_long, zone_state_lat,
                zone_state_long)
            self._attrs[ATTR_DISTANCE] = self._attrs[ATTR_DISTANCE] / 1000
            self._attrs[ATTR_DISTANCE] = round(self._attrs[ATTR_DISTANCE], 1)
        if 'battery' in new_state.attributes:
            self._attrs[ATTR_BATTERY] = new_state.attributes['battery']

        if new_state.state == self._overridestate:
            self.update_ha_state()
            return

        self._overridestate = None

        if new_state.state != 'not_home':
            self._interval = 30
            self.update_ha_state()
        else:
            if self._attrs[ATTR_DISTANCE] is None:
                self.update_ha_state()
                return
            if self._attrs[ATTR_DISTANCE] > 100:
                self._interval = round(self._attrs[ATTR_DISTANCE], 0)
                if (ATTR_GMTT in
                    self._attrs[ATTR_GMTT]):
                    gttstate = self.hass.states.get(self._attrs[ATTR_GMTT])
                    if gttstate is not None:
                        self._interval = round(float(gttstate.state) - 10, 0)
            elif self._attrs[ATTR_DISTANCE] > 50:
                self._interval = 30
            elif self._attrs[ATTR_DISTANCE] > 25:
                self._interval = 15
            elif self._attrs[ATTR_DISTANCE] > 10:
                self._interval = 5
            else:
                self._interval = 1
            if self._attrs[ATTR_BATTERY] is not None:
                if (self._attrs[ATTR_BATTERY] <= 33 and
                    self._attrs[ATTR_DISTANCE] > 3):
                    self._interval = self._interval * 2
            self.update_ha_state()


class Icloud(Entity):  # pylint: disable=too-many-instance-attributes
    """Represent an icloud account in Home Assistant."""

    def __init__(self, hass, username, password, cookiedirectory, name,
                 ignored_devices, googletraveltime):
        """Initialize an iCloud account."""
        # pylint: disable=too-many-arguments,too-many-branches
        # pylint: disable=too-many-statements,too-many-locals
        self.hass = hass
        self.username = username
        self.password = password
        self.cookiedir = cookiedirectory
        self._max_wait_seconds = 120
        self._request_interval_seconds = 10
        self._interval = 1
        self.api = None
        self.devices = {}
        self._ignored_devices = ignored_devices
        self._ignored_identifiers = {}
        self.googletraveltime = googletraveltime

        self._attrs = {}
        self._attrs[ATTR_ACCOUNTNAME] = name

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT_ICLOUD, self._attrs[ATTR_ACCOUNTNAME],
            hass=self.hass)

        if self.username is None or self.password is None:
            _LOGGER.error('Must specify a username and password')
        else:
            from pyicloud import PyiCloudService
            from pyicloud.exceptions import PyiCloudFailedLoginException
            try:
                # Attempt the login to iCloud
                self.api = PyiCloudService(
                    self.username, self.password,
                    cookie_directory=self.cookiedir, verify=True)
                for device in self.api.devices:
                    status = device.status(DEVICESTATUSSET)
                    devicename = slugify(status['name'].replace(' ', '', 99))
                    if (devicename not in self.devices and
                            devicename not in self._ignored_devices):
                        gtt = None
                        if devicename in self.googletraveltime:
                            gtt = self.googletraveltime[devicename]
                        idevice = IDevice(self.hass, self, devicename, device,
                                          gtt)
                        idevice.update_ha_state()
                        self.devices[devicename] = idevice
                    elif devicename in self._ignored_devices:
                        self._ignored_identifiers[devicename] = device

            except PyiCloudFailedLoginException as error:
                _LOGGER.error('Error logging into iCloud Service: %s',
                              error)

    @property
    def state(self):
        """Return the state of the icloud account."""
        return self.api is not None

    @property
    def state_attributes(self):
        """Return the attributes of the icloud account."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return 'mdi:account'

    @staticmethod
    def get_key(item):
        """Sort key of events."""
        return item.get('startDate')

    def keep_alive(self):
        """Keep the api alive."""
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        if self.api is None:
            from pyicloud import PyiCloudService
            from pyicloud.exceptions import PyiCloudFailedLoginException
            try:
                # Attempt the login to iCloud
                self.api = PyiCloudService(
                    self.username, self.password,
                    cookie_directory=self.cookiedir, verify=True)
            except PyiCloudFailedLoginException as error:
                _LOGGER.error('Error logging into iCloud Service: %s',
                              error)

        if self.api is not None:
            self.api.authenticate()
            for devicename in self.devices:
                self.devices[devicename].keep_alive()

    def lost_iphone(self, devicename):
        """Call the lost iphone function if the device is found."""
        if self.api is not None:
            self.api.authenticate()
            if devicename is not None:
                if devicename in self.devices:
                    self.devices[devicename].lost_iphone()
                else:
                    _LOGGER.error("devicename %s unknown for account %s",
                                  devicename, self._attrs[ATTR_ACCOUNTNAME])
            else:
                for device in self.devices:
                    self.devices[device].lost_iphone()

    def update_icloud(self, devicename=None):
        """Authenticate against iCloud and scan for devices."""
        if self.api is not None:
            from pyicloud.exceptions import PyiCloudNoDevicesException
            try:
                # The session timeouts if we are not using it so we
                # have to re-authenticate. This will send an email.
                self.api.authenticate()
                if devicename is not None:
                    if devicename in self.devices:
                        self.devices[devicename].update_icloud()
                    else:
                        _LOGGER.error("devicename %s unknown for account %s",
                                      devicename,
                                      self._attrs[ATTR_ACCOUNTNAME])
                else:
                    for device in self.devices:
                        self.devices[device].update_icloud()
            except PyiCloudNoDevicesException:
                _LOGGER.error('No iCloud Devices found!')

    def setinterval(self, interval=None, devicename=None):
        """Set the interval of the given devices."""
        if devicename is None:
            for device in self.devices:
                self.devices[device].setinterval(interval)
                self.devices[device].update_icloud()
        elif devicename in self.devices:
            self.devices[devicename].setinterval(interval)
            self.devices[devicename].update_icloud()
