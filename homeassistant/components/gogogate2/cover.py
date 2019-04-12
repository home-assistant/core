"""Support for Gogogate2 garage Doors."""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, STATE_CLOSED,
    CONF_IP_ADDRESS, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'gogogate2'

NOTIFICATION_ID = 'gogogate2_notification'
NOTIFICATION_TITLE = 'Gogogate2 Cover Setup'

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gogogate2 component."""
    from pygogogate2 import Gogogate2API as pygogogate2

    ip_address = config.get(CONF_IP_ADDRESS)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)
    username = config.get(CONF_USERNAME)

    mygogogate2 = pygogogate2(username, password, ip_address)

    try:
        devices = mygogogate2.get_devices()
        if devices is False:
            raise ValueError(
                "Username or Password is incorrect or no devices found")

        add_entities(MyGogogate2Device(
            mygogogate2, door, name) for door in devices)

    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)


class MyGogogate2Device(CoverDevice):
    """Representation of a Gogogate2 cover."""

    def __init__(self, mygogogate2, device, name):
        """Initialize with API object, device id."""
        self.mygogogate2 = mygogogate2
        self.device_id = device['door']
        self._name = name or device['name']
        self._status = device['status']
        self._available = None

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._name if self._name else DEFAULT_NAME

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._status == STATE_CLOSED

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self.mygogogate2.close_device(self.device_id)

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self.mygogogate2.open_device(self.device_id)

    def update(self):
        """Update status of cover."""
        try:
            self._status = self.mygogogate2.get_status(self.device_id)
            self._available = True
        except (TypeError, KeyError, NameError, ValueError) as ex:
            _LOGGER.error("%s", ex)
            self._status = None
            self._available = False
