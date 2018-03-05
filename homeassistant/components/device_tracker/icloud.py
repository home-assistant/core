"""
Platform that supports scanning iCloud.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/
"""
import logging
import random
import os

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DOMAIN, ATTR_ATTRIBUTES, ENTITY_ID_FORMAT, DeviceScanner)
from homeassistant.components.zone import active_zone
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util
from homeassistant.util.location import distance

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.9.1']

CONF_IGNORED_DEVICES = 'ignored_devices'
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

DEVICESTATUSCODES = {
    '200': 'online',
    '201': 'offline',
    '203': 'pending',
    '204': 'unregistered',
}

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ACCOUNTNAME): vol.All(cv.ensure_list, [cv.slugify]),
    vol.Optional(ATTR_DEVICENAME): cv.slugify,
    vol.Optional(ATTR_INTERVAL): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(ATTR_ACCOUNTNAME): cv.slugify,
})


def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Set up the iCloud Scanner."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    account = config.get(CONF_ACCOUNTNAME, slugify(username.partition('@')[0]))

    icloudaccount = Icloud(hass, username, password, account, see)

    if icloudaccount.api is not None:
        ICLOUDTRACKERS[account] = icloudaccount

    else:
        _LOGGER.error("No ICLOUDTRACKERS added")
        return False

    def lost_iphone(call):
        """Call the lost iPhone function if the device is found."""
        accounts = call.data.get(ATTR_ACCOUNTNAME, ICLOUDTRACKERS)
        devicename = call.data.get(ATTR_DEVICENAME)
        for account in accounts:
            if account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].lost_iphone(devicename)
    hass.services.register(DOMAIN, 'icloud_lost_iphone', lost_iphone,
                           schema=SERVICE_SCHEMA)

    def update_icloud(call):
        """Call the update function of an iCloud account."""
        accounts = call.data.get(ATTR_ACCOUNTNAME, ICLOUDTRACKERS)
        devicename = call.data.get(ATTR_DEVICENAME)
        for account in accounts:
            if account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].update_icloud(devicename)
    hass.services.register(DOMAIN, 'icloud_update', update_icloud,
                           schema=SERVICE_SCHEMA)

    def reset_account_icloud(call):
        """Reset an iCloud account."""
        accounts = call.data.get(ATTR_ACCOUNTNAME, ICLOUDTRACKERS)
        for account in accounts:
            if account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].reset_account_icloud()
    hass.services.register(DOMAIN, 'icloud_reset_account',
                           reset_account_icloud, schema=SERVICE_SCHEMA)

    def setinterval(call):
        """Call the update function of an iCloud account."""
        accounts = call.data.get(ATTR_ACCOUNTNAME, ICLOUDTRACKERS)
        interval = call.data.get(ATTR_INTERVAL)
        devicename = call.data.get(ATTR_DEVICENAME)
        for account in accounts:
            if account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].setinterval(interval, devicename)

    hass.services.register(DOMAIN, 'icloud_set_interval', setinterval,
                           schema=SERVICE_SCHEMA)

    # Tells the bootstrapper that the component was successfully initialized
    return True


class Icloud(DeviceScanner):
    """Representation of an iCloud account."""

    def __init__(self, hass, username, password, name, see):
        """Initialize an iCloud account."""
        self.hass = hass
        self.username = username
        self.password = password
        self.api = None
        self.accountname = name
        self.devices = {}
        self.seen_devices = {}
        self._overridestates = {}
        self._intervals = {}
        self.see = see

        self._trusted_device = None
        self._verification_code = None

        self._attrs = {}
        self._attrs[ATTR_ACCOUNTNAME] = name

        self.reset_account_icloud()

        randomseconds = random.randint(10, 59)
        track_utc_time_change(
            self.hass, self.keep_alive, second=randomseconds)

    def reset_account_icloud(self):
        """Reset an iCloud account."""
        from pyicloud import PyiCloudService
        from pyicloud.exceptions import (
            PyiCloudFailedLoginException, PyiCloudNoDevicesException)

        icloud_dir = self.hass.config.path('icloud')
        if not os.path.exists(icloud_dir):
            os.makedirs(icloud_dir)

        try:
            self.api = PyiCloudService(
                self.username, self.password,
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
                status = device.status(DEVICESTATUSSET)
                devicename = slugify(status['name'].replace(' ', '', 99))
                if devicename in self.devices:
                    _LOGGER.error('Multiple devices with name: %s', devicename)
                    continue
                self.devices[devicename] = device
                self._intervals[devicename] = 1
                self._overridestates[devicename] = None
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

        currentminutes = dt_util.now().hour * 60 + dt_util.now().minute
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
            self._intervals[devicename] = 30
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
            # home - check every half hour
            interval = 30

        if battery is not None and battery <= 33 and mindistance > 3:
            # Low battery - let's check half as often
            interval = interval * 2

        self._intervals[devicename] = interval

    def update_device(self, devicename):
        """Update the device_tracker entity."""
        from pyicloud.exceptions import PyiCloudNoDevicesException

        # An entity will not be created by see() when track=false in
        # 'known_devices.yaml', but we need to see() it at least once
        entity = self.hass.states.get(ENTITY_ID_FORMAT.format(devicename))
        if entity is None and devicename in self.seen_devices:
            return
        attrs = {}
        kwargs = {}

        if self.api is None:
            return

        try:
            for device in self.api.devices:
                if str(device) != str(self.devices[devicename]):
                    continue

                status = device.status(DEVICESTATUSSET)
                dev_id = status['name'].replace(' ', '', 99)
                dev_id = slugify(dev_id)
                attrs[ATTR_DEVICESTATUS] = DEVICESTATUSCODES.get(
                    status['deviceStatus'], 'error')
                attrs[ATTR_LOWPOWERMODE] = status['lowPowerMode']
                attrs[ATTR_BATTERYSTATUS] = status['batteryStatus']
                attrs[ATTR_ACCOUNTNAME] = self.accountname
                status = device.status(DEVICESTATUSSET)
                battery = status.get('batteryLevel', 0) * 100
                location = status['location']
                if location:
                    self.determine_interval(
                        devicename, location['latitude'],
                        location['longitude'], battery)
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
                    self.seen_devices[devicename] = True
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud Devices found")

    def lost_iphone(self, devicename):
        """Call the lost iPhone function if the device is found."""
        if self.api is None:
            return

        self.api.authenticate()

        for device in self.api.devices:
            if devicename is None or device == self.devices[devicename]:
                device.play_sound()

    def update_icloud(self, devicename=None):
        """Authenticate against iCloud and scan for devices."""
        from pyicloud.exceptions import PyiCloudNoDevicesException

        if self.api is None:
            return

        try:
            if devicename is not None:
                if devicename in self.devices:
                    self.devices[devicename].location()
                else:
                    _LOGGER.error("devicename %s unknown for account %s",
                                  devicename, self._attrs[ATTR_ACCOUNTNAME])
            else:
                for device in self.devices:
                    self.devices[device].location()
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud Devices found")

    def setinterval(self, interval=None, devicename=None):
        """Set the interval of the given devices."""
        devs = [devicename] if devicename else self.devices
        for device in devs:
            devid = '{}.{}'.format(DOMAIN, device)
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
