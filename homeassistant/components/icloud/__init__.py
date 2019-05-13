"""The iCloud component."""
import asyncio
from datetime import datetime, timedelta
import logging
import os
from pprint import pprint
import random
import sys

from pyicloud.services.findmyiphone import AppleDevice
import voluptuous as vol

from homeassistant.components.device_tracker import ENTITY_ID_FORMAT
from homeassistant.components.zone.zone import active_zone
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, track_utc_time_change)
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow
from homeassistant.util.location import distance

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'icloud'
DATA_ICLOUD = 'icloud_data'

ATTRIBUTION = "Data provided by Apple iCloud"

SIGNAL_UPDATE_ICLOUD = 'icloud_update'

SERVICE_ICLOUD_LOST_PHONE = 'icloud_lost_iphone'
SERVICE_ICLOUD_UPDATE = 'icloud_update'
SERVICE_ICLOUD_RESET = 'icloud_reset'
SERVICE_ICLOUD_SET_INTERVAL = 'icloud_set_interval'

# iCloud dev tracker comp
CONF_ACCOUNTNAME = 'account_name'
CONF_MAX_INTERVAL = 'max_interval'
CONF_GPS_ACCURACY_THRESHOLD = 'gps_accuracy_threshold'

# entity attributes
ATTR_ACCOUNTNAME = 'account_name'
ATTR_INTERVAL = 'interval'
ATTR_DEVICENAME = 'device_name'
ATTR_BATTERY = 'battery'
ATTR_DEVICESTATUS = 'device_status'
ATTR_LOWPOWERMODE = 'low_power_mode'
ATTR_BATTERYSTATUS = 'battery_status'

_CONFIGURING = {}

DEVICE_STATUS_SET = ['features', 'maxMsgChar', 'darkWake', 'fmlyShare',
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

DEVICE_STATUS_CODES = {
    '200': 'online',
    '201': 'offline',
    '203': 'pending',
    '204': 'unregistered',
}

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ACCOUNTNAME): vol.All(cv.ensure_list, [cv.slugify]),
    vol.Optional(ATTR_DEVICENAME): cv.slugify,
    vol.Optional(ATTR_INTERVAL): cv.positive_int
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(ATTR_ACCOUNTNAME): cv.slugify,
        vol.Optional(CONF_MAX_INTERVAL, default=10): cv.positive_int,
        vol.Optional(CONF_GPS_ACCURACY_THRESHOLD, default=1000): cv.positive_int
    })])
}, extra=vol.ALLOW_EXTRA)

ICLOUD_COMPONENTS = [
    'sensor', 'device_tracker'
]


def setup(hass, config):
    """Set up the iCloud component."""
    async def lost_iphone(service):
        """Call the lost iPhone function if the device is found."""
        accounts = service.data.get(ATTR_ACCOUNTNAME, hass.data[DATA_ICLOUD])
        devicename = service.data.get(ATTR_DEVICENAME)
        for account in accounts:
            if account in hass.data[DATA_ICLOUD]:
                hass.data[DATA_ICLOUD][account].lost_iphone(devicename)

    hass.services.register(DOMAIN, SERVICE_ICLOUD_LOST_PHONE, lost_iphone,
                           schema=SERVICE_SCHEMA)

    async def update_icloud(service):
        """Call the update function of an iCloud account."""
        accounts = service.data.get(ATTR_ACCOUNTNAME, hass.data[DATA_ICLOUD])
        devicename = service.data.get(ATTR_DEVICENAME)
        for account in accounts:
            if account in hass.data[DATA_ICLOUD]:
                hass.data[DATA_ICLOUD][account].update_icloud(devicename)

    hass.services.register(DOMAIN, SERVICE_ICLOUD_UPDATE, update_icloud,
                           schema=SERVICE_SCHEMA)

    async def reset_account_icloud(service):
        """Reset an iCloud account."""
        accounts = service.data.get(ATTR_ACCOUNTNAME, hass.data[DATA_ICLOUD])
        for account in accounts:
            if account in hass.data[DATA_ICLOUD]:
                hass.data[DATA_ICLOUD][account].reset_account_icloud()

        async_dispatcher_connect(
            hass, SIGNAL_UPDATE_ICLOUD, None)

    hass.services.register(DOMAIN, SERVICE_ICLOUD_RESET,
                           reset_account_icloud, schema=SERVICE_SCHEMA)

    async def setinterval(service):
        """Call the update function of an iCloud account."""
        accounts = service.data.get(ATTR_ACCOUNTNAME, hass.data[DATA_ICLOUD])
        interval = service.data.get(ATTR_INTERVAL)
        devicename = service.data.get(ATTR_DEVICENAME)
        for account in accounts:
            if account in hass.data[DATA_ICLOUD]:
                hass.data[DATA_ICLOUD][account].setinterval(interval, devicename)

    hass.services.register(DOMAIN, SERVICE_ICLOUD_SET_INTERVAL, setinterval,
                           schema=SERVICE_SCHEMA)

    def setup_icloud(icloud_config):
        """Set up an iCloud account."""
        _LOGGER.debug("Logging into iCloud...")

        username = icloud_config.get(CONF_USERNAME)
        password = icloud_config.get(CONF_PASSWORD)
        account = icloud_config.get(CONF_ACCOUNTNAME, slugify(username.partition('@')[0]))
        max_interval = icloud_config.get(CONF_MAX_INTERVAL)
        gps_accuracy_threshold = icloud_config.get(CONF_GPS_ACCURACY_THRESHOLD)

        icloud = IcloudAccount(hass, username, password, account, max_interval,
                               gps_accuracy_threshold)

        if icloud.api is not None:
            hass.data[DATA_ICLOUD][icloud.accountname] = icloud

        else:
            _LOGGER.error("No iCloud data added for account=%s", account)
            return False

        for component in ICLOUD_COMPONENTS:
            if component != 'device_tracker':
                load_platform(hass, component, DOMAIN, {}, icloud_config)

    hass.data[DATA_ICLOUD] = {}
    for icloud_account in config[DOMAIN]:
        setup_icloud(icloud_account)

    return True


class IcloudAccount():
    """Representation of an iCloud account."""

    def __init__(self, hass, username, password, name, max_interval,
                 gps_accuracy_threshold):
        """Initialize an iCloud account."""
        self.hass = hass
        self.username = username
        self.__password = password
        self.api = None
        self.accountname = name
        self.devices = {}
        self.seen_devices = {}
        self._overridestates = {}
        self._intervals = {}
        self._max_interval = max_interval
        self._gps_accuracy_threshold = gps_accuracy_threshold

        self._trusted_device = None
        self._verification_code = None

        self._attrs = {}
        self._attrs[ATTR_ACCOUNTNAME] = name

        self.reset_account_icloud()

        randomseconds = random.randint(10, 59)
        track_utc_time_change(self.hass, self.keep_alive, second=randomseconds)

        _LOGGER.info("--ICLOUD:init--")

    def reset_account_icloud(self):
        """Reset an iCloud account."""
        _LOGGER.info('ICLOUD:reset_account_icloud')
        from pyicloud import PyiCloudService
        from pyicloud.exceptions import (
            PyiCloudFailedLoginException, PyiCloudNoDevicesException)

        icloud_dir = self.hass.config.path('icloud')
        if not os.path.exists(icloud_dir):
            os.makedirs(icloud_dir)

        try:
            self.api = PyiCloudService(
                self.username, self.__password,
                cookie_directory=icloud_dir,
                verify=True)
        except PyiCloudFailedLoginException as error:
            self.api = None
            _LOGGER.error("Error logging into iCloud Service: %s", error)
            return

        try:
            self.devices = {}
            self._overridestates = {}
            self._intervals = {}
            for device in self.api.devices:
                # _LOGGER.info("--reset_account_icloud:device--")
                # pprint(vars(device))

                status = device.status(DEVICE_STATUS_SET)
                # _LOGGER.info("--reset_account_icloud:status--")
                # pprint(status)

                _LOGGER.debug('Device Status is %s', status)
                devicename = slugify(status['name'].replace(' ', '', 99))
                _LOGGER.info('Adding icloud device: %s', devicename)
                if devicename in self.devices:
                    _LOGGER.error('Multiple devices with name: %s', devicename)
                    continue
                self._intervals[devicename] = 1
                self._overridestates[devicename] = None
                self.devices[devicename] = IcloudDevice(self, device)

        except PyiCloudNoDevicesException:
            _LOGGER.error('No iCloud Devices found!')

    def icloud_trusted_device_callback(self, callback_data):
        """Handle chosen trusted devices."""
        self._trusted_device = int(callback_data.get('trusted_device'))
        self._trusted_device = self.api.trusted_devices[self._trusted_device]

        if not self.api.send_verification_code(self._trusted_device):
            _LOGGER.error("Failed to send verification code")
            self._trusted_device = None
            return

        if self.accountname in _CONFIGURING:
            request_id = _CONFIGURING.pop(self.accountname)
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)

        # Trigger the next step immediately
        self.icloud_need_verification_code()

    def icloud_need_trusted_device(self):
        """We need a trusted device."""
        configurator = self.hass.components.configurator
        if self.accountname in _CONFIGURING:
            return

        devicesstring = ''
        devices = self.api.trusted_devices
        for i, device in enumerate(devices):
            devicename = device.get(
                'deviceName', 'SMS to %s' % device.get('phoneNumber'))
            devicesstring += "{}: {};".format(i, devicename)

        _CONFIGURING[self.accountname] = configurator.request_config(
            'iCloud {}'.format(self.accountname),
            self.icloud_trusted_device_callback,
            description=(
                'Please choose your trusted device by entering'
                ' the index from this list: ' + devicesstring),
            entity_picture="/static/images/config_icloud.png",
            submit_caption='Confirm',
            fields=[{'id': 'trusted_device', 'name': 'Trusted Device'}]
        )

    def icloud_verification_callback(self, callback_data):
        """Handle the chosen trusted device."""
        from pyicloud.exceptions import PyiCloudException
        self._verification_code = callback_data.get('code')

        try:
            if not self.api.validate_verification_code(
                    self._trusted_device, self._verification_code):
                raise PyiCloudException('Unknown failure')
        except PyiCloudException as error:
            # Reset to the initial 2FA state to allow the user to retry
            _LOGGER.error("Failed to verify verification code: %s", error)
            self._trusted_device = None
            self._verification_code = None

            # Trigger the next step immediately
            self.icloud_need_trusted_device()

        if self.accountname in _CONFIGURING:
            request_id = _CONFIGURING.pop(self.accountname)
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)

    def icloud_need_verification_code(self):
        """Return the verification code."""
        configurator = self.hass.components.configurator
        if self.accountname in _CONFIGURING:
            return

        _CONFIGURING[self.accountname] = configurator.request_config(
            'iCloud {}'.format(self.accountname),
            self.icloud_verification_callback,
            description=('Please enter the validation code:'),
            entity_picture="/static/images/config_icloud.png",
            submit_caption='Confirm',
            fields=[{'id': 'code', 'name': 'code'}]
        )

    def keep_alive(self, now):
        """Keep the API alive."""
        _LOGGER.info('ICLOUD:keep_alive')
        if self.api is None:
            self.reset_account_icloud()

        if self.api is None:
            return

        if self.api.requires_2fa:
            from pyicloud.exceptions import PyiCloudException
            try:
                if self._trusted_device is None:
                    self.icloud_need_trusted_device()
                    return

                if self._verification_code is None:
                    self.icloud_need_verification_code()
                    return

                self.api.authenticate()
                if self.api.requires_2fa:
                    raise Exception('Unknown failure')

                self._trusted_device = None
                self._verification_code = None
            except PyiCloudException as error:
                _LOGGER.error("Error setting up 2FA: %s", error)
        else:
            self.api.authenticate()

        currentminutes = utcnow().hour * 60 + utcnow().minute
        try:
            for devicename in self.devices:
                interval = self._intervals.get(devicename, 1)
                if ((currentminutes % interval == 0) or
                        (interval > 10 and
                         currentminutes % interval in [2, 4])):
                    self.update_device(devicename)
        except ValueError:
            _LOGGER.debug("iCloud API returned an error")

    def determine_interval(self, devicename, latitude, longitude, battery):
        """Calculate new interval."""
        _LOGGER.info('ICLOUD:determine_interval')
        currentzone = active_zone(self.hass, latitude, longitude)

        if ((currentzone is not None and
             currentzone == self._overridestates.get(devicename)) or
                (currentzone is None and
                 self._overridestates.get(devicename) == 'away')):
            return

        zones = (self.hass.states.get(entity_id) for entity_id
                 in sorted(self.hass.states.entity_ids('zone')))

        distances = []
        for zone_state in zones:
            zone_state_lat = zone_state.attributes['latitude']
            zone_state_long = zone_state.attributes['longitude']
            zone_distance = distance(
                latitude, longitude, zone_state_lat, zone_state_long)
            distances.append(round(zone_distance / 1000, 1))

        if distances:
            mindistance = min(distances)
        else:
            mindistance = None

        self._overridestates[devicename] = None

        if currentzone is not None:
            self._intervals[devicename] = self._max_interval
            return

        if mindistance is None:
            return

        # Calculate out how long it would take for the device to drive to the
        # nearest zone at 120 km/h:
        interval = round(mindistance / 2, 0)

        # Never poll more than once per minute
        interval = max(interval, 1)

        if interval > 180:
            # Three hour drive?  This is far enough that they might be flying
            interval = 30

        if battery is not None and battery <= 33 and mindistance > 3:
            # Low battery - let's check half as often
            interval = interval * 2

        self._intervals[devicename] = interval

    def update_device(self, devicename):
        """Update the device entity."""
        from pyicloud.exceptions import PyiCloudNoDevicesException
        _LOGGER.info('-----------------------------------')
        _LOGGER.info('ICLOUD:update_device %s', devicename)

        # An entity will not be created by see() when track=false in
        # 'known_devices.yaml', but we need to see() it at least once
        entity = self.hass.states.get(ENTITY_ID_FORMAT.format(devicename))
        _LOGGER.info('ENTITY_ID_FORMAT == %s', entity)
        if entity is None and devicename in self.seen_devices:
            return

        if self.api is None:
            return

        try:
            for device in self.api.devices:
                if str(device) != str(self.devices[devicename].device):
                    continue

                _LOGGER.info('--------------------------------')
                status = device.status(DEVICE_STATUS_SET)
                if self.devices[devicename]:
                    self.devices[devicename].update(status)
                else:
                    self.devices[devicename] = IcloudDevice(self, device)

        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud Devices found")

    def lost_iphone(self, devicename):
        """Call the lost iPhone function if the device is found."""
        _LOGGER.info('ICLOUD:lost_iphone')
        if self.api is None:
            return

        self.api.authenticate()
        for device in self.api.devices:
            if str(device) == str(self.devices[devicename].device):
                _LOGGER.info("Playing Lost iPhone sound for %s", devicename)
                device.play_sound()

    def update_icloud(self, devicename=None):
        """Request device information from iCloud and update device_tracker."""
        from pyicloud.exceptions import PyiCloudNoDevicesException
        _LOGGER.info('ICLOUD:update_icloud')

        if self.api is None:
            return

        try:
            if devicename is not None:
                if devicename in self.devices:
                    self.update_device(devicename)
                else:
                    _LOGGER.error("devicename %s unknown for account %s",
                                  devicename, self._attrs[ATTR_ACCOUNTNAME])
            else:
                for device in self.devices:
                    self.update_device(device)
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud Devices found")

    def setinterval(self, interval=None, devicename=None):
        """Set the interval of the given devices."""
        _LOGGER.info('ICLOUD:setinterval')
        devs = [devicename] if devicename else self.devices
        for device in devs:
            devid = '{}.{}'.format('device_tracker', device)
            devicestate = self.hass.states.get(devid)
            if interval is not None:
                if devicestate is not None:
                    self._overridestates[device] = active_zone(
                        self.hass,
                        float(devicestate.attributes.get('latitude', 0)),
                        float(devicestate.attributes.get('longitude', 0)))
                    if self._overridestates[device] is None:
                        self._overridestates[device] = 'away'
                self._intervals[device] = interval
            else:
                self._overridestates[device] = None
            self.update_device(device)


class IcloudDevice():
    """Representation of a iCloud device."""

    def __init__(self, account, device):
        """Initialize the iCloud device."""
        _LOGGER.info('IcloudDevice:init')
        self.__account = account
        self._hass = account.hass
        self._accountname = account.accountname

        self._device = device
        self.__status = device.status(DEVICE_STATUS_SET)
        _LOGGER.debug('Device Status is %s', self.__status)

        self._name = self.__status['name']
        self._dev_id = slugify(self._name.replace(' ', '', 99))  # devicename
        self._device_class = self.__status['deviceClass']
        self._device_name = self.__status['deviceDisplayName']

        self._interval = account._intervals.get(self._dev_id, 1)

        self.update(self.__status)

        # pprint(vars(self))

    def update(self, status):
        """Update the iCloud device."""
        _LOGGER.info('IcloudDevice:update')
        self.__status = status

        self._device_status = DEVICE_STATUS_CODES.get(self.__status['deviceStatus'], 'error')

        self._attrs = {
            ATTR_ACCOUNTNAME: self._accountname,
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_DEVICENAME: self._device_name,
            ATTR_DEVICESTATUS: self._device_status,
            ATTR_INTERVAL: self._interval,
        }

        if self.__status['batteryStatus'] != 'Unknown':
            self._battery_level = round(self.__status.get('batteryLevel', 0)
                                        * 100)
            self._battery_status = self.__status['batteryStatus']
            self._low_power_mode = self.__status['lowPowerMode']

            self._attrs[ATTR_BATTERY] = self._battery_level
            self._attrs[ATTR_BATTERYSTATUS] = self._battery_status
            self._attrs[ATTR_LOWPOWERMODE] = self._low_power_mode
        
            if self.__status['location']:
                location = self.__status['location']
                self._location = location

                if location and location['horizontalAccuracy']:
                    _LOGGER.info('location %s', location)
                    horizontal_accuracy = int(location['horizontalAccuracy'])
                    if horizontal_accuracy < self.__account._gps_accuracy_threshold:
                        _LOGGER.info('horizontal_accuracy %s', horizontal_accuracy)
                        self.__account.determine_interval(
                            self._dev_id, location['latitude'],
                            location['longitude'], self._battery_level)
                        self.__account.seen_devices[self._dev_id] = True
            # self._location = {
            #     'latitude': location['latitude'],
            #     'longitude': location['longitude'],
            #     'gps_accuracy': location['horizontalAccuracy']
            # }
            # self._location.latitude = location['latitude']
            # self._location.longitude = location['longitude']
            # self._location.gps_accuracy = location['horizontalAccuracy']
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ICLOUD)

    @property
    def device(self) -> AppleDevice:
        """Return the Apple device."""
        return self._device

    @property
    def dev_id(self):
        """Return the device ID."""
        return self._dev_id

    @property
    def device_class(self):
        """Return the Apple device class."""
        return self._device_class

    @property
    def name(self):
        """Return the Apple device name."""
        return self._name

    @property
    def battery_level(self):
        """Return the Apple device battery level."""
        return self._battery_level

    @property
    def battery_status(self):
        """Return the Apple device battery status."""
        return self._battery_status

    @property
    def location(self):
        """Return the Apple device location."""
        return self._location

    @property
    def attributes(self):
        """Return the attributes."""
        return self._attrs
