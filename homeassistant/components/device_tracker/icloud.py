"""
Support for iCloud connected devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/
"""
import logging
import re

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.event import track_utc_time_change

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.8.3']

CONF_INTERVAL = 'interval'
DEFAULT_INTERVAL = 8


def setup_scanner(hass, config, see):
    """Setup the iCloud Scanner."""
    from pyicloud import PyiCloudService
    from pyicloud.exceptions import PyiCloudFailedLoginException
    from pyicloud.exceptions import PyiCloudNoDevicesException

    # Get the username and password from the configuration.
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

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

    def keep_alive(now):
        """Keep authenticating iCloud connection."""
        api.authenticate()
        _LOGGER.info("Authenticate against iCloud")

    track_utc_time_change(hass, keep_alive, second=0)

    def update_icloud(now):
        """Authenticate against iCloud and scan for devices."""
        try:
            # The session timeouts if we are not using it so we
            # have to re-authenticate. This will send an email.
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
            _LOGGER.info('No iCloud Devices found!')

    track_utc_time_change(
        hass, update_icloud,
        minute=range(0, 60, config.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
        second=0
    )

    return True
