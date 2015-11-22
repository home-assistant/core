"""
homeassistant.components.device_tracker.icloud
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning iCloud devices.

It does require that your device has beend registered with Find My iPhone.

Note: that this may cause battery drainage as it wakes up your device to
get the current location.

Note: You may receive an email from Apple stating that someone has logged
into your account.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/
"""
import logging

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.event import track_utc_time_change
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException
from pyicloud.exceptions import PyiCloudNoDevicesException
import re

SCAN_INTERVAL = 60

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/picklepete/pyicloud/archive/'
                '80f6cd6decc950514b8dc43b30c5bded81b34d5f.zip'
                '#pyicloud==0.8.0']


def setup_scanner(hass, config, see):
    """
    Set up the iCloud Scanner
    """

    # Get the username and password from the configuration
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        _LOGGER.info('Logging into iCloud Account')
        # Attempt the login to iCloud
        api = PyiCloudService(username,
                              password,
                              verify=True)
    except PyiCloudFailedLoginException as e:
        _LOGGER.exception(
            'Error logging into iCloud Service: {0}'.format(str(e))
        )

    def update_icloud(now):
        """
        Authenticate against iCloud and scan for devices.
        """
        try:
            # The session timeouts if we are not using it so we
            # have to re-authenticate.  This will send an email.
            api.authenticate()
            # Loop through every device registered with the iCloud account
            for device in api.devices:
                status = device.status()
                location = device.location()
                # If the device has a location add it. If not do nothing
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
            _LOGGER.exception('No iCloud Devices found!')

    track_utc_time_change(
        hass,
        update_icloud,
        second=range(0, 60, SCAN_INTERVAL)
    )
