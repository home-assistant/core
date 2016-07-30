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
from homeassistant.components.device_tracker import (ENTITY_ID_FORMAT,
                                                     PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyicloud==0.9.1']

CONF_INTERVAL = 'interval'
KEEPALIVE_INTERVAL = 4

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): vol.Coerce(str),
    vol.Required(CONF_PASSWORD): vol.Coerce(str),
    vol.Optional(CONF_INTERVAL, default=8): vol.All(vol.Coerce(int),
                                                    vol.Range(min=1))
    })


def setup_scanner(hass, config, see):
    """Setup the iCloud Scanner."""
    from pyicloud import PyiCloudService
    from pyicloud.exceptions import PyiCloudFailedLoginException
    from pyicloud.exceptions import PyiCloudNoDevicesException
    logging.getLogger("pyicloud.base").setLevel(logging.WARNING)

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
        """Keep authenticating iCloud connection.

        The session timeouts if we are not using it so we
        have to re-authenticate & this will send an email.
        """
        api.authenticate()
        _LOGGER.info("Authenticate against iCloud")

    seen_devices = {}

    def update_icloud(now):
        """Authenticate against iCloud and scan for devices."""
        try:
            keep_alive(None)
            # Loop through every device registered with the iCloud account
            for device in api.devices:
                status = device.status()
                dev_id = slugify(status['name'].replace(' ', '', 99))

                # An entity will not be created by see() when track=false in
                # 'known_devices.yaml', but we need to see() it at least once
                entity = hass.states.get(ENTITY_ID_FORMAT.format(dev_id))
                if entity is None and dev_id in seen_devices:
                    continue
                seen_devices[dev_id] = True

                location = device.location()
                # If the device has a location add it. If not do nothing
                if location:
                    see(
                        dev_id=dev_id,
                        host_name=status['name'],
                        gps=(location['latitude'], location['longitude']),
                        battery=status['batteryLevel']*100,
                        gps_accuracy=location['horizontalAccuracy']
                    )
        except PyiCloudNoDevicesException:
            _LOGGER.info('No iCloud Devices found!')

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, update_icloud)

    update_minutes = list(range(0, 60, config[CONF_INTERVAL]))
    # Schedule keepalives between the updates
    keepalive_minutes = list(x for x in range(0, 60, KEEPALIVE_INTERVAL)
                             if x not in update_minutes)

    track_utc_time_change(hass, update_icloud, second=0, minute=update_minutes)
    track_utc_time_change(hass, keep_alive, second=0, minute=keepalive_minutes)

    return True
