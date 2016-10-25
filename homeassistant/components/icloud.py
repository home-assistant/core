"""
Platform that supports scanning iCloud.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/icloud/
"""
import logging
import random
import re

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import (Entity, generate_entity_id)
from homeassistant.components.device_tracker import (see, ATTR_ATTRIBUTES)
from homeassistant.helpers.event import (track_state_change,
                                         track_utc_time_change)
import homeassistant.helpers.config_validation as cv
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

ENTITY_ID_FORMAT_ICLOUD = DOMAIN + '.{}'

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


def setup(hass, config):
    """Set up the iCloud Scanner."""
    # pylint: disable=too-many-locals
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
        self.api = None
        self.accountname = name
        self.devices = {}
        self._ignored_devices = ignored_devices
        self._ignored_identifiers = {}
        self.googletraveltime = googletraveltime
        self._overridestates = {}
        self._intervals = {}

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
                        track_state_change(
                            self.hass, 'device_tracker.' + devicename,
                            self.devicechanged)
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

    def keep_alive(self, now):
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
            for device in self.api.devices:
                if (device not in self.devices.values() and
                        device not in self._ignored_identifiers.values()):
                    status = device.status(DEVICESTATUSSET)
                    devicename = slugify(status['name'].replace(' ', '', 99))
                    if (devicename not in self.devices and
                            devicename not in self._ignored_devices):
                        track_state_change(
                            self.hass, 'device_tracker.' + devicename,
                            self.devicechanged)
                        self.devices[devicename] = device
                        self._intervals[devicename] = 1
                        self._overridestates[devicename] = None
                    elif devicename in self._ignored_devices:
                        self._ignored_identifiers[devicename] = device
            for devicename in self.devices:
                self.update_device(devicename)

    def devicechanged(self, entity, old_state, new_state):
        """Calculate new interval."""
        # pylint: disable=too-many-branches
        if entity is None:
            return

        devicename = re.sub('device_tracker.', '', entity)

        distancefromhome = None
        if 'latitude' in new_state.attributes:
            device_state_lat = new_state.attributes['latitude']
            device_state_long = new_state.attributes['longitude']
            zone_state = self.hass.states.get('zone.home')
            zone_state_lat = zone_state.attributes['latitude']
            zone_state_long = zone_state.attributes['longitude']
            distancefromhome = distance(
                device_state_lat, device_state_long, zone_state_lat,
                zone_state_long)
            distancefromhome = round(distancefromhome / 1000, 1)
        if 'battery' in new_state.attributes:
            battery = new_state.attributes['battery']

        if new_state.state == self._overridestates.get(devicename):
            return

        self._overridestates[devicename] = None

        if new_state.state != 'not_home':
            self._intervals[devicename] = 30
        else:
            if distancefromhome is None:
                self.update_ha_state()
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
        orig_int = new_state.attributes.get(ATTR_INTERVAL, 1)
        if self._intervals[devicename] != orig_int:
            self.update_device(devicename)

    def update_device(self, devicename):
        """Update the device_tracker entity."""
        # pylint: disable=too-many-branches,too-many-statements
        # pylint: disable=too-many-nested-blocks,too-many-locals
        devstate = self.hass.states.get('device_tracker.' + devicename)
        attrs = {}
        kwargs = {}
        if devstate is not None:
            gtt = self.googletraveltime.get(devicename)
            if gtt is not None:
                gttstate = self.hass.states.get(gtt)
                if gttstate is not None:
                    if 'origin_addresses' in gttstate.attributes:
                        duration = gttstate.state
                        origin = gttstate.attributes['origin_addresses']
                        attrs[ATTR_GMTT_DURATION] = duration
                        attrs[ATTR_GMTT_ORIGIN] = origin

            currentminutes = dt_util.now().hour * 60 + dt_util.now().minute
            interval = self._intervals.get(devicename, 1)
            if ((currentminutes % interval == 0) or
                    (interval > 10 and currentminutes % interval in [2, 4])):
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
                                attrs[ATTR_INTERVAL] = interval
                                attrs[ATTR_ACCOUNTNAME] = self.accountname
                                status = device.status(DEVICESTATUSSET)
                                battery = status['batteryLevel']*100
                                location = status['location']
                                if location:
                                    accuracy = location['horizontalAccuracy']
                                    kwargs['hass'] = self.hass
                                    kwargs['dev_id'] = dev_id
                                    kwargs['host_name'] = status['name']
                                    kwargs['gps'] = (location['latitude'],
                                                     location['longitude'])
                                    kwargs['battery'] = battery
                                    kwargs['gps_accuracy'] = accuracy
                                    kwargs[ATTR_ATTRIBUTES] = attrs
                                    see(**kwargs)
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
        for device in self.devices:
            if devicename is None or device == devicename:
                devid = 'device_tracker.' + devicename
                devicestate = self.hass.states.get(devid)
                if interval is not None:
                    if devicestate is not None:
                        self._overridestates[devicename] = devicestate.state
                    self._intervals[devicename] = interval
                else:
                    self._overridestates[devicename] = None
                    self.devicechanged('device_tracker.' + devicename, None,
                                       devicestate)
                self.update_device(devicename)
