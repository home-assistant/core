"""
Platform that supports scanning iCloud.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker/icloud/
"""
import logging
import random

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DOMAIN, ATTR_ATTRIBUTES)
from homeassistant.components.zone import active_zone
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util
from homeassistant.util.location import distance
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.9.1']

CONF_IGNORED_DEVICES = 'ignored_devices'
CONF_GMTT = 'google_maps_travel_time'
CONF_COOKIEDIRECTORY = 'cookiedirectory'
CONF_ACCOUNTNAME = 'account_name'

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

_CONFIGURING = {}

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(ATTR_ACCOUNTNAME): cv.slug,
    vol.Optional(CONF_COOKIEDIRECTORY, default=None): cv.string,
    vol.Optional(CONF_IGNORED_DEVICES, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_GMTT, default={}):
        vol.Schema({cv.string: cv.string}),
})


def setup_scanner(hass, config: dict, see):
    """Set up the iCloud Scanner."""
    # pylint: disable=too-many-locals
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    account = config.get(CONF_ACCOUNTNAME, slugify(username))
    cookiedirectory = config.get(CONF_COOKIEDIRECTORY)

    ignored_devices = []
    ignored_dev = config.get(CONF_IGNORED_DEVICES)
    for each_dev in ignored_dev:
        ignored_devices.append(each_dev)

    googletraveltime = {}
    gttconfig = config.get(CONF_GMTT)
    for google, googleconfig in gttconfig.items():
        googletraveltime[google] = googleconfig

    icloudaccount = Icloud(hass, username, password, cookiedirectory,
                           account, ignored_devices, googletraveltime, see)
    ICLOUDTRACKERS[account] = icloudaccount

    if not ICLOUDTRACKERS:
        _LOGGER.error("No ICLOUDTRACKERS added")
        return False

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

    def reset_account_icloud(call):
        """Reset an icloud account."""
        accountname = call.data.get(ATTR_ACCOUNTNAME)
        if accountname is None:
            for account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].reset_account_icloud()
        elif accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].reset_account_icloud()
    hass.services.register(DOMAIN,
                           'reset_account_icloud', reset_account_icloud)

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


class Icloud(object):  # pylint: disable=too-many-instance-attributes
    """Represent an icloud account in Home Assistant."""

    def __init__(self, hass, username, password, cookiedirectory, name,
                 ignored_devices, googletraveltime, see):
        """Initialize an iCloud account."""
        # pylint: disable=too-many-arguments,too-many-branches
        # pylint: disable=too-many-statements,too-many-locals
        self.hass = hass
        self.username = username
        self.password = password
        self.cookiedir = cookiedirectory
        self.api = None
        self.accountname = name
        self.devices = {}
        self._ignored_devices = ignored_devices
        self._ignored_identifiers = {}
        self.googletraveltime = googletraveltime
        self._overridestates = {}
        self._intervals = {}
        self.see = see

        self._trusted_device = None
        self._verification_code = None

        self._attrs = {}
        self._attrs[ATTR_ACCOUNTNAME] = name

        if self.username is None or self.password is None:
            _LOGGER.error('Must specify a username and password')
        else:
            from pyicloud import PyiCloudService
            from pyicloud.exceptions import PyiCloudFailedLoginException
            try:
                self.api = PyiCloudService(
                    self.username, self.password,
                    cookie_directory=self.cookiedir, verify=True)
                for device in self.api.devices:
                    status = device.status(DEVICESTATUSSET)
                    devicename = slugify(status['name'].replace(' ', '', 99))
                    if (devicename not in self.devices and
                            devicename not in self._ignored_devices):
                        self.devices[devicename] = device
                        self._intervals[devicename] = 1
                        self._overridestates[devicename] = None
                    elif devicename in self._ignored_devices:
                        self._ignored_identifiers[devicename] = device

            except PyiCloudFailedLoginException as error:
                _LOGGER.error('Error logging into iCloud Service: %s',
                              error)

        randomseconds = random.randint(10, 59)
        track_utc_time_change(
            self.hass, self.keep_alive,
            second=randomseconds
        )

    def reset_account_icloud(self):
        """Reset an icloud account."""
        from pyicloud import PyiCloudService
        from pyicloud.exceptions import PyiCloudFailedLoginException
        try:
            self.api = PyiCloudService(
                self.username, self.password,
                cookie_directory=self.cookiedir, verify=True)
            for device in self.api.devices:
                status = device.status(DEVICESTATUSSET)
                devicename = slugify(status['name'].replace(' ', '', 99))
                if (devicename not in self.devices and
                        devicename not in self._ignored_devices):
                    self.devices[devicename] = device
                    self._intervals[devicename] = 1
                    self._overridestates[devicename] = None
                elif devicename in self._ignored_devices:
                    self._ignored_identifiers[devicename] = device

        except PyiCloudFailedLoginException as error:
            _LOGGER.error('Error logging into iCloud Service: %s', error)

    def icloud_trusted_device_callback(self, callback_data):
        """The trusted device is chosen."""
        self._trusted_device = int(callback_data.get('0', '0'))
        self._trusted_device = self.api.trusted_devices[self._trusted_device]
        if self.accountname in _CONFIGURING:
            request_id = _CONFIGURING.pop(self.accountname)
            configurator = get_component('configurator')
            configurator.request_done(request_id)

    def icloud_need_trusted_device(self):
        """We need a trusted device."""
        configurator = get_component('configurator')
        if self.accountname in _CONFIGURING:
            return

        devicesstring = ''
        devices = self.api.trusted_devices
        for i, device in enumerate(devices):
            devicesstring += "{}: {};".format(i, device.get('deviceName'))

        _CONFIGURING[self.accountname] = configurator.request_config(
            self.hass, 'iCloud {}'.format(self.accountname),
            self.icloud_trusted_device_callback,
            description=(
                'Please choose your trusted device by entering'
                ' the index from this list: ' + devicesstring),
            description_image="/static/images/config_icloud.png",
            submit_caption='Confirm',
            fields=[{'id': '0'}]
        )

    def icloud_verification_callback(self, callback_data):
        """The trusted device is chosen."""
        self._verification_code = callback_data.get('0')
        if self.accountname in _CONFIGURING:
            request_id = _CONFIGURING.pop(self.accountname)
            configurator = get_component('configurator')
            configurator.request_done(request_id)

    def icloud_need_verification_code(self):
        """We need a verification code."""
        configurator = get_component('configurator')
        if self.accountname in _CONFIGURING:
            return

        if self.api.send_verification_code(self._trusted_device):
            self._verification_code = 'waiting'

        _CONFIGURING[self.accountname] = configurator.request_config(
            self.hass, 'iCloud {}'.format(self.accountname),
            self.icloud_verification_callback,
            description=('Please enter the validation code:'),
            description_image="/static/images/config_icloud.png",
            submit_caption='Confirm',
            fields=[{'code': '0'}]
        )

    def keep_alive(self, now):
        """Keep the api alive."""
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        if self.api is None:
            from pyicloud import PyiCloudService
            from pyicloud.exceptions import PyiCloudFailedLoginException
            try:
                self.api = PyiCloudService(
                    self.username, self.password,
                    cookie_directory=self.cookiedir, verify=True)
            except PyiCloudFailedLoginException as error:
                _LOGGER.error('Error logging into iCloud Service: %s',
                              error)

        if self.api is not None:
            if self.api.requires_2fa:
                from pyicloud.exceptions import PyiCloud2FARequiredError
                try:
                    self.api.authenticate()
                except PyiCloud2FARequiredError as error:
                    if self._trusted_device is None:
                        self.icloud_need_trusted_device()
                        return

                    if self._verification_code is None:
                        self.icloud_need_verification_code()
                        return

                    if self._verification_code == 'waiting':
                        return

                    if self.api.validate_verification_code(
                            self._trusted_device, self._verification_code):
                        self._verification_code = None
            else:
                self.api.authenticate()

            currentminutes = dt_util.now().hour * 60 + dt_util.now().minute
            for devicename in self.devices:
                interval = self._intervals.get(devicename, 1)
                if ((currentminutes % interval == 0) or
                        (interval > 10 and
                         currentminutes % interval in [2, 4])):
                    self.update_device(devicename)

    def determine_interval(self, devicename, latitude, longitude, battery):
        """Calculate new interval."""
        # pylint: disable=too-many-branches
        distancefromhome = None
        zone_state = self.hass.states.get('zone.home')
        zone_state_lat = zone_state.attributes['latitude']
        zone_state_long = zone_state.attributes['longitude']
        distancefromhome = distance(latitude, longitude, zone_state_lat,
                                    zone_state_long)
        distancefromhome = round(distancefromhome / 1000, 1)

        currentzone = active_zone(self.hass, latitude, longitude)

        if ((currentzone is not None and
             currentzone == self._overridestates.get(devicename)) or
                (currentzone is None and
                 self._overridestates.get(devicename) == 'away')):
            return

        self._overridestates[devicename] = None

        if currentzone is not None:
            self._intervals[devicename] = 30
        else:
            if distancefromhome is None:
                return
            if distancefromhome > 100:
                self._intervals[devicename] = round(distancefromhome, 0)
                gtt = self.googletraveltime.get(devicename)
                if gtt is not None:
                    gttstate = self.hass.states.get(gtt)
                    if gttstate is not None:
                        self._intervals[devicename] = round(
                            float(gttstate.state) - 10, 0)
            elif distancefromhome > 50:
                self._intervals[devicename] = 30
            elif distancefromhome > 25:
                self._intervals[devicename] = 15
            elif distancefromhome > 10:
                self._intervals[devicename] = 5
            else:
                self._intervals[devicename] = 1
            if battery is not None and battery <= 33 and distancefromhome > 3:
                self._intervals[devicename] = self._intervals[devicename] * 2

    def update_device(self, devicename):
        """Update the device_tracker entity."""
        # pylint: disable=too-many-branches,too-many-statements
        # pylint: disable=too-many-nested-blocks,too-many-locals
        attrs = {}
        kwargs = {}
        gtt = self.googletraveltime.get(devicename)
        if gtt is not None:
            gttstate = self.hass.states.get(gtt)
            if gttstate is not None:
                if 'origin_addresses' in gttstate.attributes:
                    duration = gttstate.state
                    origin = gttstate.attributes['origin_addresses']
                    attrs[ATTR_GMTT_DURATION] = duration
                    attrs[ATTR_GMTT_ORIGIN] = origin

        if self.api is not None:
            from pyicloud.exceptions import PyiCloudNoDevicesException
            try:
                for device in self.api.devices:
                    if str(device) == str(self.devices[devicename]):
                        status = device.status(DEVICESTATUSSET)
                        dev_id = status['name'].replace(' ', '', 99)
                        dev_id = slugify(dev_id)
                        devicestatuscode = status['deviceStatus']
                        if devicestatuscode == '200':
                            attrs[ATTR_DEVICESTATUS] = 'online'
                        elif devicestatuscode == '201':
                            attrs[ATTR_DEVICESTATUS] = 'offline'
                        elif devicestatuscode == '203':
                            attrs[ATTR_DEVICESTATUS] = 'pending'
                        elif devicestatuscode == '204':
                            attrs[ATTR_DEVICESTATUS] = 'unregistered'
                        else:
                            attrs[ATTR_DEVICESTATUS] = 'error'
                        lowpowermode = status['lowPowerMode']
                        attrs[ATTR_LOWPOWERMODE] = lowpowermode
                        batterystatus = status['batteryStatus']
                        attrs[ATTR_BATTERYSTATUS] = batterystatus
                        attrs[ATTR_ACCOUNTNAME] = self.accountname
                        status = device.status(DEVICESTATUSSET)
                        battery = status['batteryLevel']*100
                        location = status['location']
                        if location:
                            self.determine_interval(devicename,
                                                    location['latitude'],
                                                    location['longitude'],
                                                    battery)
                            interval = self._intervals.get(devicename, 1)
                            attrs[ATTR_INTERVAL] = interval
                            accuracy = location['horizontalAccuracy']
                            kwargs['dev_id'] = dev_id
                            kwargs['host_name'] = status['name']
                            kwargs['gps'] = (location['latitude'],
                                             location['longitude'])
                            kwargs['battery'] = battery
                            kwargs['gps_accuracy'] = accuracy
                            kwargs[ATTR_ATTRIBUTES] = attrs
                            self.see(**kwargs)
            except PyiCloudNoDevicesException:
                _LOGGER.error('No iCloud Devices found!')

    def lost_iphone(self, devicename):
        """Call the lost iphone function if the device is found."""
        if self.api is not None:
            self.api.authenticate()

            for device in self.api.devices:
                if devicename is None or device == self.devices[devicename]:
                    device.play_sound()

    def update_icloud(self, devicename=None):
        """Authenticate against iCloud and scan for devices."""
        if self.api is not None:
            from pyicloud.exceptions import PyiCloudNoDevicesException
            try:
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
        for device in self.devices:
            if devicename is None or device == devicename:
                if devicename is None:
                    devname = device
                else:
                    devname = devicename
                devid = DOMAIN + '.' + devname
                devicestate = self.hass.states.get(devid)
                if interval is not None:
                    if devicestate is not None:
                        self._overridestates[devname] = active_zone(
                            self.hass,
                            float(devicestate.attributes.get('latitude', 0)),
                            float(devicestate.attributes.get('longitude', 0)))
                        if self._overridestates[devname] is None:
                            self._overridestates[devname] = 'away'
                    self._intervals[devname] = interval
                else:
                    self._overridestates[devname] = None
                self.update_device(devname)
