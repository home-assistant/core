"""
Support for MyQ-Enabled Garage Doors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.myq/
"""
import logging

import voluptuous as vol

from homeassistant.components.cover import CoverDevice
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_TYPE, STATE_CLOSED)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pymyq==0.0.8']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'myq'

NOTIFICATION_ID = 'myq_notification'
NOTIFICATION_TITLE = 'MyQ Cover Setup'

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MyQ component."""
    from pymyq import MyQAPI as pymyq

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    brand = config.get(CONF_TYPE)
    myq = pymyq(username, password, brand)

    try:
        if not myq.is_supported_brand():
            raise ValueError("Unsupported type. See documentation")

        if not myq.is_login_valid():
            raise ValueError("Username or Password is incorrect")

        add_devices(MyQDevice(myq, door) for door in myq.get_garage_doors())
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


class MyQDevice(CoverDevice):
    """Representation of a MyQ cover."""

    def __init__(self, myq, device):
        """Initialize with API object, device id."""
        self.myq = myq
        self.device_id = device['deviceid']
        self._name = device['name']
        self._status = STATE_CLOSED

    @property
    def should_poll(self):
        """Poll for state."""
        return True

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._name if self._name else DEFAULT_NAME

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._status == STATE_CLOSED

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self.myq.close_device(self.device_id)

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self.myq.open_device(self.device_id)

    def update(self):
        """Update status of cover."""
        self._status = self.myq.get_status(self.device_id)
