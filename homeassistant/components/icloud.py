"""
Platform that supports scanning iCloud.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/icloud/
"""
import logging
from datetime import datetime, timedelta
from math import floor
import random
import re

from pytz import timezone
import pytz

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.device_tracker import see
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.event import track_time_change
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.util.dt as dt_util
from homeassistant.util.location import distance

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.9.1']

DEPENDENCIES = ['zone', 'device_tracker']

CONF_EVENTS = 'events'
DEFAULT_EVENTS = False

CONF_COOKIEDIRECTORY = 'cookiedirectory'

# entity attributes
ATTR_ACCOUNTNAME = 'accountname'
ATTR_INTERVAL = 'interval'
ATTR_DEVICENAME = 'devicename'
ATTR_BATTERY = 'battery'
ATTR_DISTANCE = 'distance'
ATTR_STARTTIME = 'start_time'
ATTR_ENDTIME = 'end_time'
ATTR_DURATION = 'duration'
ATTR_REMAINING = 'remaining_time'
ATTR_DEVICESTATUS = 'device_status'
ATTR_LOWPOWERMODE = 'low_power_mode'
ATTR_BATTERYSTATUS = 'battery_status'
ATTR_LOCATION = 'location'
ATTR_FRIENDLY_NAME = 'friendly_name'
ATTR_GOOGLE_MAPS_TRAVEL_TIME = 'google_maps_travel_time'
ATTR_GOOGLE_MAPS_TRAVEL_TIME_DURATION = 'gmtt_duration'
ATTR_GOOGLE_MAPS_TRAVEL_TIME_ORIGIN = 'gmtt_origin'

TYPE_CURRENT = 'currentevent'
TYPE_NEXT = 'nextevent'

ICLOUDTRACKERS = {}

DOMAIN = 'icloud'
DOMAIN2 = 'idevice'
DOMAIN3 = 'ievent'

ENTITY_ID_FORMAT_ICLOUD = DOMAIN + '.{}'
ENTITY_ID_FORMAT_DEVICE = DOMAIN2 + '.{}'
ENTITY_ID_FORMAT_EVENT = DOMAIN3 + '.{}'

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


def setup(hass, config): # pylint: disable=too-many-locals,too-many-branches
    """Set up the iCloud Scanner."""
    if config.get(DOMAIN) is None:
        return False

    for account, account_config in config[DOMAIN].items():

        if not isinstance(account_config, dict):
            _LOGGER.error("Missing configuration data for account %s", account)
            continue

        if CONF_USERNAME not in account_config:
            _LOGGER.error("Missing username for account %s", account)
            continue

        if CONF_PASSWORD not in account_config:
            _LOGGER.error("Missing password for account %s", account)
            continue

        # Get the username and password from the configuration
        username = account_config.get(CONF_USERNAME)
        password = account_config.get(CONF_PASSWORD)
        cookiedirectory = account_config.get(CONF_COOKIEDIRECTORY, None)

        ignored_devices = []
        if 'ignored_devices' in account_config:
            ignored_dev = account_config.get('ignored_devices')
            for each_dev in ignored_dev:
                ignored_devices.append(each_dev)

        getevents = account_config.get(CONF_EVENTS, DEFAULT_EVENTS)

        googletraveltime = {}
        if 'googletraveltime' in account_config:
            gttconfig = account_config.get('googletraveltime')
            for google, googleconfig in gttconfig.items():
                googletraveltime[google] = googleconfig

        icloudaccount = Icloud(hass, username, password, cookiedirectory,
                               account, ignored_devices, getevents,
                               googletraveltime)
        icloudaccount.update_ha_state()
        ICLOUDTRACKERS[account] = icloudaccount
        if ICLOUDTRACKERS[account].api is not None:
            for device in ICLOUDTRACKERS[account].devices:
                iclouddevice = ICLOUDTRACKERS[account].devices[device]
                devicename = iclouddevice.devicename.lower()
                track_state_change(hass,
                                   'device_tracker.' + devicename,
                                   iclouddevice.devicechanged)

        if 'manual_update' in account_config:
            def update_now(now):
                """Update the account, the devices and the events."""
                ICLOUDTRACKERS[account].update_icloud()

            manual_update = account_config.get('manual_update')
            for each_time in manual_update:
                each_time = dt_util.parse_time(each_time)
                track_time_change(hass, update_now,
                                  hour=each_time.hour,
                                  minute=each_time.minute,
                                  second=each_time.second)

    if not ICLOUDTRACKERS:
        _LOGGER.error("No ICLOUDTRACKERS added")
        return False

    randomseconds = random.randint(10, 59)

    def lost_iphone(call):
        """Call the lost iphone function if the device is found."""
        accountname = call.data.get('accountname')
        devicename = call.data.get('devicename')
        if accountname is None:
            for account in ICLOUDTRACKERS:
                ICLOUDTRACKERS[account].lost_iphone(devicename)
        elif accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].lost_iphone(devicename)

    hass.services.register(DOMAIN, 'lost_iphone',
                           lost_iphone)

    def update_icloud(call):
        """Call the update function of an icloud account."""
        accountname = call.data.get('accountname')
        devicename = call.data.get('devicename')
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
        accountname = call.data.get('accountname')
        interval = call.data.get('interval')
        devicename = call.data.get('devicename')
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
        self.devicename = name
        self.identifier = identifier
        self._request_interval_seconds = 60
        self._interval = 1
        self.api = icloudobject.api
        self._distance = None
        self._battery = None
        self._overridestate = None
        self._devicestatuscode = None
        self._devicestatus = None
        self._lowpowermode = None
        self._batterystatus = None
        self._googletraveltime = googletraveltime
        self._gttduration = None
        self._gttorigin = None

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT_DEVICE, self.devicename,
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
        """Return the friendlyname of the iDevice."""
        if self._googletraveltime is None:
            return {
                ATTR_DEVICENAME: self.devicename,
                ATTR_BATTERY: self._battery,
                ATTR_DISTANCE: self._distance,
                ATTR_DEVICESTATUS: self._devicestatus,
                ATTR_LOWPOWERMODE: self._lowpowermode,
                ATTR_BATTERYSTATUS: self._batterystatus,
                ATTR_GOOGLE_MAPS_TRAVEL_TIME: self._googletraveltime
            }
        else:
            return {
                ATTR_DEVICENAME: self.devicename,
                ATTR_BATTERY: self._battery,
                ATTR_DISTANCE: self._distance,
                ATTR_DEVICESTATUS: self._devicestatus,
                ATTR_LOWPOWERMODE: self._lowpowermode,
                ATTR_BATTERYSTATUS: self._batterystatus,
                ATTR_GOOGLE_MAPS_TRAVEL_TIME: self._googletraveltime,
                ATTR_GOOGLE_MAPS_TRAVEL_TIME_DURATION:
                    self._gttduration,
                ATTR_GOOGLE_MAPS_TRAVEL_TIME_ORIGIN:
                    self._gttorigin
            }

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return 'mdi:cellphone-iphone'

    def keep_alive(self):
        """Keep the api alive."""
        currentminutes = dt_util.now().hour * 60 + dt_util.now().minute
        if currentminutes % self._interval == 0:
            self.update_icloud()
        elif self._interval > 10 and currentminutes % self._interval == 2:
            self.update_icloud()
        elif self._interval > 10 and currentminutes % self._interval == 4:
            self.update_icloud()

        self._gttduration = None
        self._gttorigin = None
        if self._googletraveltime is not None:
            gttstate = self.hass.states.get(self._googletraveltime)
            if gttstate is not None:
                if 'origin_addresses' in gttstate.attributes:
                    self._gttduration = gttstate.state
                    self._gttorigin = gttstate.attributes['origin_addresses']
                    self.update_ha_state()

    def lost_iphone(self):
        """Call the lost iphone function if the device is found."""
        if self.api is not None:
            self.api.authenticate()
            self.identifier.play_sound()

    def data_is_accurate(data):
        """Check if location data is accurate."""
        if not data:
            return False
        elif not data['locationFinished']:
            return False
        return True

    def update_icloud(self, ):
        """Authenticate against iCloud and scan for devices."""
        if self.api is not None:
            from pyicloud.exceptions import PyiCloudNoDevicesException

            try:
                # Loop through every device registered with the iCloud account
                status = self.identifier.status(DEVICESTATUSSET)
                dev_id = re.sub(r"(\s|\W|')", '',
                                status['name']).lower()
                self._devicestatuscode = status['deviceStatus']
                if self._devicestatuscode == '200':
                    self._devicestatus = 'online'
                elif self._devicestatuscode == '201':
                    self._devicestatus = 'offline'
                elif self._devicestatuscode == '203':
                    self._devicestatus = 'pending'
                elif self._devicestatuscode == '204':
                    self._devicestatus = 'unregistered'
                else:
                    self._devicestatus = 'error'
                self._lowpowermode = status['lowPowerMode']
                self._batterystatus = status['batteryStatus']
                self.update_ha_state()
                status = self.identifier.status(DEVICESTATUSSET)
                battery = status['batteryLevel']*100
                location = status['location']
                if location:
                    see(
                        hass=self.hass,
                        dev_id=dev_id,
                        host_name=status['name'],
                        gps=(location['latitude'],
                             location['longitude']),
                        battery=battery,
                        gps_accuracy=location['horizontalAccuracy']
                    )
            except PyiCloudNoDevicesException:
                _LOGGER.error('No iCloud Devices found!')

    def get_default_interval(self):
        """Get default interval of iDevice."""
        devid = 'device_tracker.' + self.devicename
        devicestate = self.hass.states.get(devid)
        self._overridestate = None
        self.devicechanged(self.devicename, None, devicestate)

    def setinterval(self, interval=None):
        """Set interval of iDevice."""
        if interval is not None:
            devid = 'device_tracker.' + self.devicename
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
        if entity is None:
            return

        self._distance = None
        if 'latitude' in new_state.attributes:
            device_state_lat = new_state.attributes['latitude']
            device_state_long = new_state.attributes['longitude']
            zone_state = self.hass.states.get('zone.home')
            zone_state_lat = zone_state.attributes['latitude']
            zone_state_long = zone_state.attributes['longitude']
            self._distance = distance(device_state_lat, device_state_long,
                                      zone_state_lat, zone_state_long)
            self._distance = round(self._distance / 1000, 1)
        if 'battery' in new_state.attributes:
            self._battery = new_state.attributes['battery']

        if new_state.state == self._overridestate:
            self.update_ha_state()
            return

        self._overridestate = None

        if new_state.state != 'not_home':
            self._interval = 30
            self.update_ha_state()
        else:
            if self._distance is None:
                self.update_ha_state()
                return
            if self._distance > 100:
                self._interval = round(self._distance, 0)
                if self._googletraveltime is not None:
                    gttstate = self.hass.states.get(self._googletraveltime)
                    if gttstate is not None:
                        self._interval = round(float(gttstate.state) - 10, 0)
            elif self._distance > 50:
                self._interval = 30
            elif self._distance > 25:
                self._interval = 15
            elif self._distance > 10:
                self._interval = 5
            else:
                self._interval = 1
            if self._battery is not None:
                if self._battery <= 33 and self._distance > 3:
                    self._interval = self._interval * 2
            self.update_ha_state()

class IEvent(Entity):  # pylint: disable=too-many-instance-attributes
    """Represent an icloud calendar event in Home Assistant."""

    def __init__(self, hass, icloudobject, name, typeevent=None):
        """Initialize an iEvent."""
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.icloudobject = icloudobject
        self.api = icloudobject.api
        self.eventguid = name
        self._starttime = None
        self._starttext = None
        self._endtime = None
        self._endtext = None
        self._duration = None
        self._title = None
        self._remaining = 0
        self._remainingtext = None
        self._location = None
        self._type = typeevent
        self._tz = None

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT_EVENT, self.eventguid,
            hass=self.hass)

    @property
    def state(self):
        """Return the state of the icloud event."""
        return self._title

    @property
    def state_attributes(self):
        """Return the attributes of the icloud event."""
        return {
            ATTR_STARTTIME: self._starttext,
            ATTR_ENDTIME: self._endtext,
            ATTR_DURATION: self._duration,
            ATTR_REMAINING: self._remainingtext,
            ATTR_LOCATION: self._location,
            ATTR_FRIENDLY_NAME: self._type
        }

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        if self._type == TYPE_CURRENT:
            return 'mdi:calendar'
        elif self._type == TYPE_NEXT:
            return 'mdi:calendar-clock'

    def keep_alive(self, starttime, endtime, duration, title, tzone, location):
        """Keep the api alive."""
        current = self._type == TYPE_CURRENT
        nextev = self._type == TYPE_NEXT
        self._remaining = 0
        tempnow = dt_util.now(tzone)
        if tzone is None:
            self._tz = pytz.utc
        else:
            self._tz = tzone

        if starttime is None:
            self._starttime = None
            self._starttext = None
        else:
            self._starttime = datetime(starttime[1], starttime[2],
                                       starttime[3], starttime[4],
                                       starttime[5], 0, 0, self._tz)
            self._starttext = self._starttime.strftime("%A %d %B %Y %H.%M.%S")
            if nextev:
                self._remaining = self._starttime - tempnow
                remainingdays = self._remaining.days
                remainingseconds = (self._starttime.hour * 3600 +
                                    self._starttime.minute * 60 +
                                    self._starttime.second -
                                    tempnow.hour * 3600 -
                                    tempnow.minute * 60 -
                                    tempnow.second)
                if ((self._starttime.year > tempnow.year or
                     self._starttime.month > tempnow.month or
                     self._starttime.day > tempnow.day) and
                        remainingseconds < 0):
                    remainingseconds = 86400 + remainingseconds
                self._remaining = (remainingdays * 1440 +
                                   round(remainingseconds / 60, 0))
        if endtime is None:
            self._endtime = None
            self._endtext = None
        else:
            self._endtime = datetime(endtime[1], endtime[2], endtime[3],
                                     endtime[4], endtime[5], 0, 0,
                                     self._tz)
            self._endtext = self._endtime.strftime("%A %d %B %Y %H.%M.%S")
            if current:
                self._remaining = self._endtime - tempnow
                remainingdays = self._remaining.days
                remainingseconds = (self._endtime.hour * 3600 +
                                    self._endtime.minute * 60 +
                                    self._endtime.second -
                                    tempnow.hour * 3600 -
                                    tempnow.minute * 60 -
                                    tempnow.second)
                if ((self._endtime.year > tempnow.year or
                     self._endtime.month > tempnow.month or
                     self._endtime.day > tempnow.day) and
                        remainingseconds < 0):
                    remainingseconds = 86400 + remainingseconds
                self._remaining = (remainingdays * 1440 +
                                   round(remainingseconds / 60, 0))
        self._duration = duration
        self._title = title
        if (current or nextev) and title is None:
            self._title = 'Free'
        self._location = location

        tempdays = floor(self._remaining / 1440)
        temphours = floor((self._remaining % 1440) / 60)
        tempminutes = floor(self._remaining % 60)
        self._remainingtext = (str(tempdays) + "d " +
                               str(temphours) + "h " +
                               str(tempminutes) + "m")

        if self._remaining <= 0:
            self.hass.states.remove(self.entity_id)
        else:
            self.update_ha_state()

    def check_alive(self):
        """Check if event is over."""
        current = self._type == TYPE_CURRENT
        nextev = self._type == TYPE_NEXT
        self._remaining = 0
        tempnow = dt_util.now(self._tz)
        if self._starttime is not None:
            if nextev:
                self._remaining = self._starttime - tempnow
                remainingdays = self._remaining.days
                remainingseconds = (self._starttime.hour * 3600 +
                                    self._starttime.minute * 60 +
                                    self._starttime.second -
                                    tempnow.hour * 3600 -
                                    tempnow.minute * 60 -
                                    tempnow.second)
                if ((self._starttime.year > tempnow.year or
                     self._starttime.month > tempnow.month or
                     self._starttime.day > tempnow.day) and
                        remainingseconds < 0):
                    remainingseconds = 86400 + remainingseconds
                self._remaining = (remainingdays * 1440 +
                                   round(remainingseconds / 60, 0))
        if self._endtime is not None:
            if current:
                self._remaining = self._endtime - tempnow
                remainingdays = self._remaining.days
                remainingseconds = (self._endtime.hour * 3600 +
                                    self._endtime.minute * 60 +
                                    self._endtime.second -
                                    tempnow.hour * 3600 -
                                    tempnow.minute * 60 -
                                    tempnow.second)
                if ((self._endtime.year > tempnow.year or
                     self._endtime.month > tempnow.month or
                     self._endtime.day > tempnow.day) and
                        remainingseconds < 0):
                    remainingseconds = 86400 + remainingseconds
                self._remaining = (remainingdays * 1440 +
                                   round(remainingseconds / 60, 0))

        tempdays = floor(self._remaining / 1440)
        temphours = floor((self._remaining % 1440) / 60)
        tempminutes = floor(self._remaining % 60)
        self._remainingtext = (str(tempdays) + "d " +
                               str(temphours) + "h " +
                               str(tempminutes) + "m")

        if self._remaining <= 0:
            self.hass.states.remove(self.entity_id)
        else:
            self.update_ha_state()

class Icloud(Entity):  # pylint: disable=too-many-instance-attributes
    """Represent an icloud account in Home Assistant."""

    def __init__(self, hass, username, password, cookiedirectory, name,
                 ignored_devices, getevents, googletraveltime):
        """Initialize an iCloud account."""
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.username = username
        self.password = password
        self.cookiedirectory = cookiedirectory
        self.accountname = name
        self._max_wait_seconds = 120
        self._request_interval_seconds = 10
        self._interval = 1
        self.api = None
        self.devices = {}
        self.getevents = getevents
        self.events = {}
        self.currentevents = {}
        self.nextevents = {}
        self._ignored_devices = ignored_devices
        self._ignored_identifiers = {}
        self.googletraveltime = googletraveltime

        self._currentevents = 0
        self._nextevents = 0

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT_ICLOUD, self.accountname,
            hass=self.hass)

        if self.username is None or self.password is None:
            _LOGGER.error('Must specify a username and password')
        else:
            try:
                # Attempt the login to iCloud
                self.api = PyiCloudService(self.username,
                                           self.password,
                                           cookie_directory=
                                           self.cookiedirectory,
                                           verify=True)
                for device in self.api.devices:
                    status = device.status(DEVICESTATUSSET)
                    devicename = re.sub(r"(\s|\W|')", '',
                                        status['name']).lower()
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

                if self.getevents:
                    from_dt = dt_util.now()
                    to_dt = from_dt + timedelta(days=7)
                    events = self.api.calendar.events(from_dt, to_dt)
                    new_events = sorted(events, key=self.get_key)
                    starttime = None
                    endtime = None
                    duration = None
                    title = None
                    tzone = pytz.utc
                    location = None
                    guid = None
                    for event in new_events:
                        tzone = event['tz']
                        if tzone is None:
                            tzone = pytz.utc
                        else:
                            tzone = timezone(tzone)
                        tempnow = dt_util.now(tzone)
                        guid = event['guid']
                        starttime = event['startDate']
                        startdate = datetime(starttime[1], starttime[2],
                                             starttime[3], starttime[4],
                                             starttime[5], 0, 0, tzone)
                        endtime = event['endDate']
                        enddate = datetime(endtime[1], endtime[2], endtime[3],
                                           endtime[4], endtime[5], 0, 0, tzone)
                        duration = event['duration']
                        title = event['title']
                        location = event['location']

                        strnow = tempnow.strftime("%Y%m%d%H%M%S")
                        strstart = startdate.strftime("%Y%m%d%H%M%S")
                        strend = enddate.strftime("%Y%m%d%H%M%S")

                        if strnow > strstart and strend > strnow:
                            ievent = IEvent(self.hass, self, guid,
                                            TYPE_CURRENT)
                            ievent.update_ha_state()
                            self.currentevents[guid] = ievent
                            self.currentevents[guid].keep_alive(starttime,
                                                                endtime,
                                                                duration,
                                                                title,
                                                                tzone,
                                                                location)

                        starttime = None
                        endtime = None
                        duration = None
                        title = None
                        tzone = pytz.utc
                        location = None
                        guid = None

                    starttime = None
                    endtime = None
                    duration = None
                    title = None
                    tzone = pytz.utc
                    location = None
                    guid = None
                    for event in new_events:
                        tzone = event['tz']
                        if tzone is None:
                            tzone = pytz.utc
                        else:
                            tzone = timezone(tzone)
                        tempnow = dt_util.now(tzone)
                        guid = event['guid']
                        starttime = event['startDate']
                        startdate = datetime(starttime[1],
                                             starttime[2],
                                             starttime[3],
                                             starttime[4],
                                             starttime[5], 0, 0, tzone)
                        endtime = event['endDate']
                        enddate = datetime(endtime[1], endtime[2],
                                           endtime[3], endtime[4],
                                           endtime[5], 0, 0, tzone)
                        duration = event['duration']
                        title = event['title']
                        location = event['location']

                        strnow = tempnow.strftime("%Y%m%d%H%M%S")
                        strstart = startdate.strftime("%Y%m%d%H%M%S")
                        strend = enddate.strftime("%Y%m%d%H%M%S")

                        if strnow < strstart:
                            ievent = IEvent(self.hass, self, guid,
                                            TYPE_NEXT)
                            ievent.update_ha_state()
                            self.nextevents[guid] = ievent
                            self.nextevents[guid].keep_alive(starttime,
                                                             endtime,
                                                             duration,
                                                             title,
                                                             tzone,
                                                             location)

            except Exception as error:
                _LOGGER.error('Error logging into iCloud Service: %s',
                              error)

    @property
    def state(self):
        """Return the state of the icloud account."""
        return self.api is not None

    @property
    def state_attributes(self):
        """Return the attributes of the icloud account."""
        if self.getevents:
            return {
                ATTR_ACCOUNTNAME: self.accountname,
                'current events': self._currentevents,
                'next events': self._nextevents
            }
        else:
            return {
                ATTR_ACCOUNTNAME: self.accountname
            }

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return 'mdi:account'

    def get_key(item):
        """Sort key of events."""
        return item.get('startDate')

    def keep_alive(self):
        """Keep the api alive."""
        if self.api is None:
            try:
                # Attempt the login to iCloud
                self.api = PyiCloudService(self.username,
                                           self.password,
                                           cookie_directory=
                                           self.cookiedirectory,
                                           verify=True)

            except PyiCloudFailedLoginException as error:
                _LOGGER.error('Error logging into iCloud Service: %s',
                              error)

        if self.api is not None:
            self.api.authenticate()
            for devicename in self.devices:
                self.devices[devicename].keep_alive()
            if self.getevents:
                from_dt = dt_util.now()
                to_dt = from_dt + timedelta(days=7)
                events = self.api.calendar.events(from_dt, to_dt)
                new_events = sorted(events, key=self.get_key)
                starttime = None
                endtime = None
                duration = None
                title = None
                tzone = pytz.utc
                location = None
                guid = None
                for event in new_events:
                    tzone = event['tz']
                    if tzone is None:
                        tzone = pytz.utc
                    else:
                        tzone = timezone(tzone)
                    tempnow = dt_util.now(tzone)
                    guid = event['guid']
                    starttime = event['startDate']
                    startdate = datetime(starttime[1], starttime[2],
                                         starttime[3], starttime[4],
                                         starttime[5], 0, 0, tzone)
                    endtime = event['endDate']
                    enddate = datetime(endtime[1], endtime[2], endtime[3],
                                       endtime[4], endtime[5], 0, 0, tzone)
                    duration = event['duration']
                    title = event['title']
                    location = event['location']

                    strnow = tempnow.strftime("%Y%m%d%H%M%S")
                    strstart = startdate.strftime("%Y%m%d%H%M%S")
                    strend = enddate.strftime("%Y%m%d%H%M%S")

                    if strnow > strstart and strend > strnow:
                        if guid not in self.currentevents:
                            ievent = IEvent(self.hass, self, guid,
                                            TYPE_CURRENT)
                            ievent.update_ha_state()
                            self.currentevents[guid] = ievent
                        self.currentevents[guid].keep_alive(starttime,
                                                            endtime,
                                                            duration,
                                                            title,
                                                            tzone,
                                                            location)
                    starttime = None
                    endtime = None
                    duration = None
                    title = None
                    tzone = pytz.utc
                    location = None
                    guid = None

                for addedevent in self.currentevents:
                    found = False
                    eventguid = self.currentevents[addedevent].eventguid
                    for event in new_events:
                        if event['guid'] == eventguid:
                            found = True
                    if not found:
                        ent_id = generate_entity_id(ENTITY_ID_FORMAT_EVENT,
                                                    eventguid,
                                                    hass=self.hass)
                        self.hass.states.remove(ent_id)
                        del self.currentevents[addedevent]
                    else:
                        self.currentevents[addedevent].check_alive()

                starttime = None
                endtime = None
                duration = None
                title = None
                tzone = pytz.utc
                location = None
                guid = None
                for event in new_events:
                    tzone = event['tz']
                    if tzone is None:
                        tzone = pytz.utc
                    else:
                        tzone = timezone(tzone)
                    tempnow = dt_util.now(tzone)
                    guid = event['guid']
                    starttime = event['startDate']
                    startdate = datetime(starttime[1],
                                         starttime[2],
                                         starttime[3],
                                         starttime[4],
                                         starttime[5], 0, 0, tzone)
                    endtime = event['endDate']
                    enddate = datetime(endtime[1], endtime[2],
                                       endtime[3], endtime[4],
                                       endtime[5], 0, 0, tzone)
                    duration = event['duration']
                    title = event['title']
                    location = event['location']

                    strnow = tempnow.strftime("%Y%m%d%H%M%S")
                    strstart = startdate.strftime("%Y%m%d%H%M%S")
                    strend = enddate.strftime("%Y%m%d%H%M%S")

                    if strnow < strstart:
                        if guid not in self.nextevents:
                            ievent = IEvent(self.hass, self, guid,
                                            TYPE_NEXT)
                            ievent.update_ha_state()
                            self.nextevents[guid] = ievent
                        self.nextevents[guid].keep_alive(starttime,
                                                         endtime,
                                                         duration,
                                                         title,
                                                         tzone,
                                                         location)
                for addedevent in self.nextevents:
                    found = False
                    eventguid = self.nextevents[addedevent].eventguid
                    for event in new_events:
                        if event['guid'] == eventguid:
                            found = True
                    if not found:
                        ent_id = generate_entity_id(ENTITY_ID_FORMAT_EVENT,
                                                    eventguid,
                                                    hass=self.hass)
                        self.hass.states.remove(ent_id)
                        del self.nextevents[addedevent]
                    else:
                        self.nextevents[addedevent].check_alive()

                self._currentevents = 0
                self._nextevents = 0
                for entity_id in self.hass.states.entity_ids('ievent'):
                    state = self.hass.states.get(entity_id)
                    friendlyname = state.attributes.get(ATTR_FRIENDLY_NAME)
                    if friendlyname == 'nextevent':
                        self._nextevents = self._nextevents + 1
                    elif friendlyname == 'currentevent':
                        self._currentevents = self._currentevents + 1
                self.update_ha_state()

    def lost_iphone(self, devicename):
        """Call the lost iphone function if the device is found."""
        if self.api is not None:
            self.api.authenticate()
            if devicename is not None:
                if devicename in self.devices:
                    self.devices[devicename].lost_iphone()
                else:
                    _LOGGER.error("devicename %s unknown for account %s",
                                  devicename, self.accountname)
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
                                      devicename, self.accountname)
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
