"""
Support for iCloud connected devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/
"""
import logging
import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.9.1']

CONF_INTERVAL = 'interval'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): vol.Coerce(str),
    vol.Required(CONF_PASSWORD): vol.Coerce(str),
    vol.Optional(CONF_INTERVAL, default=8): vol.Coerce(int)
    }, extra=vol.ALLOW_EXTRA)


def setup_scanner(hass, config, see):
    """Setup the iCloud Scanner."""
    from pyicloud import PyiCloudService
    from pyicloud.exceptions import PyiCloudFailedLoginException
    from pyicloud.exceptions import PyiCloudNoDevicesException

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        _LOGGER.info('Logging into iCloud Account')
        # Attempt the login to iCloud
        api = PyiCloudService(username, password, verify=True)
    except PyiCloudFailedLoginException as error:
        _LOGGER.exception('Error logging into iCloud Service: %s', error)
        return False

    def keep_alive(now):
        """Keep authenticating iCloud connection."""
        api.authenticate()
        _LOGGER.info("Authenticate against iCloud")

    track_utc_time_change(hass, keep_alive, second=0, minute=4)

    def update_icloud(now):
        """Authenticate against iCloud and scan for devices."""
        try:
            # The session timeouts if we are not using it so we
            # have to re-authenticate. This will send an email.
            keep_alive(None)
            # Loop through every device registered with the iCloud account
            for device in api.devices:
                status = device.status()
                location = device.location()
                # If the device has a location add it. If not do nothing
                if location:
                    see(
                        dev_id=slugify(status['name']),
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

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, update_icloud)

    track_utc_time_change(hass, update_icloud, second=0,
                          minute=range(0, 60, config[CONF_INTERVAL]))

    return True
