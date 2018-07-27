import logging

import voluptuous as vol

from homeassistant.components.cover import (CoverDevice, PLATFORM_SCHEMA,
                                            SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, STATE_CLOSED,
                                 STATE_OPENING, STATE_CLOSING, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['aladdin_connect==0.1']

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = 'aladdin_notification'
NOTIFICATION_TITLE = 'Aladdin Connect Cover Setup'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Aladdin Connect component."""
    from aladdin_connect import AladdinConnectClient

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    acc = AladdinConnectClient(username, password)

    try:
        if not acc.login():
            raise ValueError("Username or Password is incorrect")
        add_devices(AladdinDevice(acc, door) for door in acc.get_doors())
        return True
    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False


class AladdinDevice(CoverDevice):
    """Representation of Aladdin Connect cover"""

    def __init__(self, acc, device):
        self._acc = acc
        self._device_id = device['device_id']
        self._number = device['door_number']
        self._name = device['name']
        self._status = device['status']

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def should_poll(self):
        """Poll for state."""
        return True

    @property
    def name(self):
        """Return the name of the garage door."""
        return self._name

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._status == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._status == STATE_CLOSING

    @property
    def is_closed(self):
        """Return None if status is unknown, true if closed, else False."""
        if self._status == STATE_UNKNOWN:
            return None
        return self._status == STATE_CLOSED

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self._acc.close_door(self._device_id, self._number)

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self._acc.open_door(self._device_id, self._number)

    def update(self):
        """Update status of cover."""
        self._status = self._acc.get_door_status(self._device_id, self._number)
