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


def setup_scanner(hass, config, see):
    """ Set up the iCloud Scanner. """
    from pyicloud import PyiCloudService
    from pyicloud.exceptions import PyiCloudFailedLoginException
    from pyicloud.exceptions import PyiCloudNoDevicesException

    # Get the username and password from the configuration
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME, username)

    if username is None or password is None:
        _LOGGER.error('Must specify a username and password')
        return False

    try:
        _LOGGER.info('Logging into iCloud Account')
        # Attempt the login to iCloud
        api = PyiCloudService(username,
                              password,
                              verify=True)
    except PyiCloudFailedLoginException as error:
        _LOGGER.exception('Error logging into iCloud Service: %s', error)
        return False

    def lost_iphone(hostname):
        """ Calls the lost iphone function if the device is found """
        api.authenticate()
        for device in api.devices:
            status = device.status()
            _LOGGER.info('lost_iphone: check device %s', status['name'])
            if hostname == status['name']:
                _LOGGER.info('lost_iphone: device %s found, playing sound',
                             status['name'])
                device.play_sound()

    def lost_iphone_service(call):
        """Handle a calls to the lost iphone services."""
        _LOGGER.info('lost_iphone called for %s', call.data.get('devicename'))
        lost_iphone(call.data.get('devicename'))

    hass.services.register('device_tracker', 'lost_iphone_' + name,
                           lost_iphone_service)

    def update_icloud(now):
        """ Authenticate against iCloud and scan for devices. """
        try:
            # The session timeouts if we are not using it so we
            # have to re-authenticate. This will send an email.
            api.authenticate()
            # Loop through every device registered with the iCloud account
            for device in api.devices:
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

    hass.services.register('device_tracker',
                           'update_icloud_' + name, update_icloud)
    hass.services.call('device_tracker', 'update_icloud_' + name)

    track_utc_time_change(
        hass, update_icloud,
        minute=range(0, 60, config.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
        second=0
    )

    return True
