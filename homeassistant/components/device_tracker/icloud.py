"""
homeassistant.components.device_tracker.icloud
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning iCloud devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/
"""
import logging

import re
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from homeassistant.helpers.event import track_utc_time_change

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.7.2']

CONF_INTERVAL = 'interval'
DEFAULT_INTERVAL = 8

# entity attributes
ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'
ATTR_ACCOUNTNAME = 'accountname'

ICLOUDTRACKERS = {}


def setup_scanner(hass, config, see):
    """ Set up the iCloud Scanner. """

    # Get the username and password from the configuration
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME, username)

    iclouddevice = Icloud(hass, username, password, name)
    ICLOUDTRACKERS[name] = iclouddevice

    def lost_iphone(call):
        """ Calls the lost iphone function if the device is found """
        accountname = call.data.get('accountname')
        devicename = call.data.get('devicename')
        if accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].lost_iphone(devicename)

    hass.services.register('device_tracker', 'lost_iphone',
                           lost_iphone)

    def update_icloud(call):
        """ Calls the update function of an icloud account """
        accountname = call.data.get('accountname')
        if accountname in ICLOUDTRACKERS:
            ICLOUDTRACKERS[accountname].update_icloud(see)

    hass.services.register('device_tracker',
                           'update_icloud', update_icloud)
    iclouddevice.update_icloud(see)

    track_utc_time_change(
        hass, iclouddevice.update_icloud(see),
        minute=range(0, 60, config.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
        second=0
    )

    return True


class Icloud(object):  # pylint: disable=too-many-instance-attributes
    """ Represents a Proximity in Home Assistant. """
    def __init__(self, hass, username, password, name):
        # pylint: disable=too-many-arguments
        from pyicloud import PyiCloudService
        from pyicloud.exceptions import PyiCloudFailedLoginException

        self.hass = hass
        self.username = username
        self.password = password
        self.accountname = name
        self.api = None

        if self.username is None or self.password is None:
            _LOGGER.error('Must specify a username and password')
        else:
            try:
                _LOGGER.info('Logging into iCloud Account')
                # Attempt the login to iCloud
                self.api = PyiCloudService(self.username,
                                           self.password,
                                           verify=True)
            except PyiCloudFailedLoginException as error:
                _LOGGER.exception('Error logging into iCloud Service: %s',
                                  error)

    @property
    def state(self):
        """ returns the state of the icloud tracker """
        return self.api is not None

    @property
    def state_attributes(self):
        """ returns the friendlyname of the icloud tracker """
        return {
            ATTR_ACCOUNTNAME: self.accountname
        }

    def lost_iphone(self, devicename):
        """ Calls the lost iphone function if the device is found """
        if self.api is not None:
            self.api.authenticate()
            for device in self.api.devices:
                status = device.status()
                if devicename is None or devicename == status['name']:
                    device.play_sound()

    def update_icloud(self, see):
        """ Authenticate against iCloud and scan for devices. """
        if self.api is not None:
            from pyicloud.exceptions import PyiCloudNoDevicesException

            try:
                # The session timeouts if we are not using it so we
                # have to re-authenticate. This will send an email.
                self.api.authenticate()
                # Loop through every device registered with the iCloud account
                for device in self.api.devices:
                    status = device.status()
                    location = device.location()
                    if location:
                        see(
                            dev_id=re.sub(r"(\s|\W|')",
                                          '',
                                          status['name']),
                            host_name=status['name'],
                            gps=(location['latitude'], location['longitude']),
                            battery=status['batteryLevel']*100,
                            gps_accuracy=location['horizontalAccuracy']
                        )
                    else:
                        # No location found for the device so continue
                        continue
            except PyiCloudNoDevicesException:
                _LOGGER.info('No iCloud Devices found!')
